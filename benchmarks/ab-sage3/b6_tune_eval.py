"""
Evaluate ab_b6_tune.py outputs: SSIM/PSNR vs the 8-step base of the same prompt (ffmpeg filters),
mean Laplacian sharpness and frame-to-frame flicker, plus one contact sheet per prompt
(rows = variants, 4 frames each).

Usage (repo root):
    env_uv/Scripts/python.exe benchmarks/ab-sage3/b6_tune_eval.py [--tag TAG]
"""
import argparse
import json
import os
import re
import subprocess

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = (0, 13, 26, 40)


def ffmpeg_metric(a, b, filt):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", a, "-i", b, "-lavfi", f"[0:v][1:v]{filt}", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    if filt == "ssim":
        m = re.search(r"All:([\d.]+)", out)
    else:
        m = re.search(r"average:([\d.]+|inf)", out)
    return float(m.group(1)) if m else None


def read_frames(path):
    cap, frames = cv2.VideoCapture(path), []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    return frames


def stats(frames):
    gray = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frames]
    sharp = float(np.mean([cv2.Laplacian(g, cv2.CV_32F).var() for g in gray]))
    flicker = float(np.mean([np.abs(gray[i + 1] - gray[i]).mean() for i in range(len(gray) - 1)]))
    return round(sharp, 1), round(flicker, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    sfx = f"_{args.tag}" if args.tag else ""
    results = json.load(open(os.path.join(HERE, f"b6_tune_results{sfx}.json"), encoding="utf-8"))
    results = [r for r in results if r["variant"] != "warmup" and r["file"]]
    base = {r["prompt"]: r["file"] for r in results if r["variant"] == "base8"}
    sheets = {}
    for r in results:
        frames = read_frames(r["file"])
        r["frames"] = len(frames)
        r["sharpness"], r["flicker"] = stats(frames)
        ref = base.get(r["prompt"])
        if ref and r["variant"] != "base8":
            r["ssim_vs_base8"] = ffmpeg_metric(r["file"], ref, "ssim")
            r["psnr_vs_base8"] = ffmpeg_metric(r["file"], ref, "psnr")
        row = np.concatenate([cv2.resize(frames[min(i, len(frames) - 1)], (416, 240)) for i in FRAMES], axis=1)
        cv2.putText(row, f"{r['variant']} {r['seconds']}s", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
        cv2.putText(row, f"{r['variant']} {r['seconds']}s", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        sheets.setdefault(r["prompt"], []).append(row)
    for p, rows in sheets.items():
        cv2.imwrite(os.path.join(HERE, f"b6_tune_sheet{sfx}_{p}.jpg"), np.concatenate(rows, axis=0), [cv2.IMWRITE_JPEG_QUALITY, 85])
    hdr = f"{'variant':10} {'p':2} {'sec':>6} {'MB':>5} {'ssim':>6} {'psnr':>6} {'sharp':>7} {'flick':>6}"
    print(hdr)
    for r in results:
        print(f"{r['variant']:10} {r['prompt']:2} {r['seconds']:6} {r['size_mb']:5} {r.get('ssim_vs_base8') or '':>6} "
              f"{r.get('psnr_vs_base8') or '':>6} {r['sharpness']:7} {r['flicker']:6}")
    json.dump(results, open(os.path.join(HERE, f"b6_tune_eval{sfx}.json"), "w", encoding="utf-8"), indent=2)


if __name__ == "__main__":
    main()
