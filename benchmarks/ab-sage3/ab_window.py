"""
A/B the LTX2.5 upsampler sliding window: fewer windows = less duplicated work.

`spatial_upsamplers.ltx2.window_size` is a server config key (not per task), so
this script backs up wgp_config.json, writes the window, runs the queue, and
always restores the original config (try/finally), even on failure.

window_starts(frames, window, overlap=17): frames <= window -> 1 window;
otherwise starts step by (window - overlap), so 121 frames / window 81 -> 2
windows and 138 frames processed instead of 121 (+14% wasted).

Usage:
    env_uv/Scripts/python.exe benchmarks/ab-sage3/ab_window.py --window 81  --frames 89
    env_uv/Scripts/python.exe benchmarks/ab-sage3/ab_window.py --window 481 --frames 89
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
PY = os.path.join(REPO_ROOT, "env_uv", "Scripts", "python.exe")
CONFIG = os.path.join(REPO_ROOT, "wgp_config.json")

sys.path.insert(0, REPO_ROOT)
from postprocessing.ltx2_upsampler.runtime import window_starts  # noqa: E402

MODEL = "ltx2_25_22B_redgraft_nsfw"
PROMPT = "A cinematic drone shot flying over a coastal road at sunset, waves crashing on rocks below."
WIN_RE = re.compile(r"(\d+)/(\d+) \[([0-9:.]+)<[^\]]*, *([0-9.]+)s/window\]")


def set_window(window):
    """Write window_size, return the original text so it can be restored verbatim."""
    original = open(CONFIG, encoding="utf-8").read()
    data = json.loads(original)
    data.setdefault("spatial_upsamplers", {}).setdefault("ltx2", {})["window_size"] = window
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return original


class VramSampler:
    """Peak VRAM during the run (the skill asks for peak device memory, not just time)."""

    def __init__(self, interval=0.5):
        self.interval = interval
        self.peak_mb = 0
        self._stop = threading.Event()
        self._thread = None

    def _loop(self):
        while not self._stop.is_set():
            try:
                out = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5)
                for line in out.stdout.strip().splitlines():
                    value = int(line.strip())
                    if value > self.peak_mb:
                        self.peak_mb = value
            except Exception:
                pass
            self._stop.wait(self.interval)

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, required=True)
    ap.add_argument("--frames", type=int, default=89)
    args = ap.parse_args()

    task = {
        "prompt": PROMPT, "negative_prompt": "", "alt_prompt": "",
        "batch_size": 1, "repeat_generation": 1, "seed": 1234, "image_mode": 0,
        "multi_prompts_gen_type": "PW", "image_prompt_type": "",
        "settings_version": 2.79, "model_type": MODEL,
        "num_inference_steps": 8, "video_length": args.frames,
        "resolution": "832x480", "spatial_upsampling": "ltx25*2",
    }
    queue = os.path.join(HERE, f"win_queue_{args.window}.json")
    with open(queue, "w", encoding="utf-8") as f:
        json.dump([task], f, indent=2, ensure_ascii=False)

    starts = window_starts(args.frames, args.window, 17)
    processed = sum(min(args.window, args.frames - s) for s in starts)
    print(f"window={args.window} frames={args.frames} -> {len(starts)} window(s), "
          f"{processed} frames processed (queue {args.frames})", flush=True)

    out_dir = os.path.join(HERE, f"out-win{args.window}")
    os.makedirs(out_dir, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("PROCESSOR_ARCHITECTURE", "AMD64")

    original = set_window(args.window)
    sampler = VramSampler()
    sampler.start()
    t0 = time.time()
    per_window = []
    try:
        cmd = [PY, "wgp.py", "--process", queue, "--output-dir", out_dir]
        proc = subprocess.Popen(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", bufsize=1, env=env)
        log = []
        for raw in proc.stdout:
            line = raw.rstrip()
            log.append(f"[{time.time()-t0:8.1f}] {line}")
            m = WIN_RE.search(line)
            if m:
                per_window.append(float(m.group(4)))
            if any(k in line for k in ("Queue completed", "s/window", "Task 1/", "OOM", "out of memory")):
                print(f"[{time.time()-t0:7.1f}s] {line[:130]}", flush=True)
        proc.wait()
        rc = proc.returncode
        with open(os.path.join(HERE, f"win{args.window}_timeline.log"), "w", encoding="utf-8") as f:
            f.write("\n".join(log))
    finally:
        sampler.stop()
        with open(CONFIG, "w", encoding="utf-8") as f:
            f.write(original)
        print("config restored", flush=True)

    total = time.time() - t0
    print(f"\nwindow={args.window} frames={args.frames}: exit={rc} total={total:.1f}s "
          f"({len(starts)} window(s))")
    print(f"  peak VRAM: {sampler.peak_mb} MB")
    if per_window:
        print(f"  per-window (app timer): {[round(w,1) for w in per_window]} s")
        print(f"  sum per-window: {sum(per_window):.1f}s")


if __name__ == "__main__":
    main()
