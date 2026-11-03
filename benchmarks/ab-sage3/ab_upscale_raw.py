"""
Raw-timeline diagnosis of the LTX2.5 Pixel Upscaler slowdown.

Captures EVERY stdout line of wgp.py --process with a wall-clock timestamp, so
nothing is lost to filters. Two tasks:
  1) 832x480 base generation, no upscale
  2) 832x480 + LTX2.5 Pixel Upscaler x2
Frames are reduced (41) to keep a diagnostic run short; the structural question
is where the seconds go, not the absolute total.

Usage:
    env_uv/Scripts/python.exe benchmarks/ab-sage3/ab_upscale_raw.py [--frames 41]
"""

import argparse
import json
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
PY = os.path.join(REPO_ROOT, "env_uv", "Scripts", "python.exe")

MODEL = "ltx2_25_22B_redgraft_nsfw"
PROMPT = "A cinematic drone shot flying over a coastal road at sunset, waves crashing on rocks below."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=41)
    args = ap.parse_args()

    common = {
        "prompt": PROMPT, "negative_prompt": "", "alt_prompt": "",
        "batch_size": 1, "repeat_generation": 1, "seed": 1234, "image_mode": 0,
        "multi_prompts_gen_type": "PW", "image_prompt_type": "",
        "settings_version": 2.79, "model_type": MODEL,
        "num_inference_steps": 8, "video_length": args.frames,
        "resolution": "832x480",
    }
    tasks = [dict(common), dict(common, spatial_upsampling="ltx25*2")]
    queue = os.path.join(HERE, "raw_queue.json")
    with open(queue, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)

    out_dir = os.path.join(HERE, "out-raw")
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(HERE, "raw_timeline.log")
    cmd = [PY, "wgp.py", "--process", queue, "--output-dir", out_dir]
    env = dict(os.environ)
    env.setdefault("PROCESSOR_ARCHITECTURE", "AMD64")

    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", bufsize=1, env=env)
    with open(log_path, "w", encoding="utf-8") as lf:
        for raw in proc.stdout:
            el = time.time() - t0
            line = raw.rstrip()
            lf.write(f"[{el:8.1f}] {line}\n")
            lf.flush()
            if line.startswith("[Task") or "Queue completed" in line:
                print(f"[{el:8.1f}s] {line}", flush=True)
    proc.wait()
    print(f"\nexit={proc.returncode} total={time.time()-t0:.1f}s")
    print("raw log:", log_path)


if __name__ == "__main__":
    main()
