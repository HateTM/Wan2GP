"""
Phase breakdown of an H3 (MiniMax H3 10Eros) generation.

Timestamps every stdout line and prints the wall time between phase changes, so
the split between model load, text conditioning, denoising, VAE decode and save
becomes visible. The user reports H3 quality is better than LTX-2.5, so H3 is the
model worth optimizing.

Usage:
    env_uv/Scripts/python.exe benchmarks/ab-sage3/ab_h3_phases.py [--frames 41]
"""

import argparse
import json
import os
import re
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
PY = os.path.join(REPO_ROOT, "env_uv", "Scripts", "python.exe")

PHASE_RE = re.compile(r"\[\s*(\d+)/(\d+)\]\s*Prompt\s*(\d+)/(\d+)\s*-\s*([^|]+)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=41)
    args = ap.parse_args()

    task = {
        "prompt": "A cinematic drone shot flying over a coastal road at sunset, waves crashing on rocks below.",
        "negative_prompt": "", "alt_prompt": "", "batch_size": 1, "repeat_generation": 1,
        "seed": 1234, "image_mode": 0, "multi_prompts_gen_type": "PW", "image_prompt_type": "",
        "settings_version": 2.79, "model_type": "minimax_h3_10eros_max_b5_fl2va",
        "num_inference_steps": 8, "video_length": args.frames, "resolution": "832x480",
        "sample_solver": "res_multistep", "guidance_scale": 1.0, "guidance_phases": 1,
        "flow_shift": 12.0,
    }
    queue = os.path.join(HERE, "h3_phase_queue.json")
    with open(queue, "w", encoding="utf-8") as f:
        json.dump([task], f, indent=2, ensure_ascii=False)

    out_dir = os.path.join(HERE, "out-h3-phase")
    os.makedirs(out_dir, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("PROCESSOR_ARCHITECTURE", "AMD64")
    cmd = [PY, "wgp.py", "--process", queue, "--output-dir", out_dir]
    print("cmd:", " ".join(cmd), flush=True)

    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", bufsize=1, env=env)
    events = []
    for raw in proc.stdout:
        line = raw.rstrip()
        el = time.time() - t0
        m = PHASE_RE.search(line)
        label = None
        if m:
            label = m.group(5).strip()
        elif "Queue completed" in line or line.startswith("[Task"):
            label = line[:70]
        if label:
            events.append((el, label))
            print(f"[{el:7.1f}s] {label[:80]}", flush=True)
    proc.wait()
    total = time.time() - t0

    # collapse consecutive duplicates
    seq = []
    for el, lab in events:
        if seq and seq[-1][1] == lab:
            seq[-1] = (el, lab)
        else:
            seq.append((el, lab))

    print(f"\nexit={proc.returncode} total={total:.1f}s")
    print("\nфаза -> длительность")
    for i, (el, lab) in enumerate(seq):
        nxt = seq[i + 1][0] if i + 1 < len(seq) else total
        dur = nxt - el
        if dur >= 0.5:
            print(f"  {el:7.1f}s .. {nxt:7.1f}s  ({dur:7.1f}s)  {lab[:70]}")


if __name__ == "__main__":
    main()
