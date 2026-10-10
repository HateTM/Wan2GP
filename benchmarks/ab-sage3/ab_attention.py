"""
A/B: sage2 vs sage3 on the same real generation queue (LTX-2.5 REDGraft 22B).

Runs `wgp.py --process` twice with --attention sage2 / sage3, times each task
from the driver process by watching the "[Task i/N]" lines, and prints the
comparison. The first task of the queue is a warmup that pays the model load
and is excluded from the table.

Usage (from the repo root):
    env_uv/Scripts/python.exe benchmarks/ab-sage3/ab_attention.py
"""

import json
import os
import re
import subprocess
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = os.path.join(REPO_ROOT, "env_uv", "Scripts", "python.exe")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL = "ltx2_25_22B_redgraft_nsfw"
PROMPT = (
    "A cinematic drone shot flying over a coastal road at sunset, waves crashing "
    "on rocks below, warm golden light, smooth continuous camera movement."
)

COMMON = {
    "prompt": PROMPT,
    "negative_prompt": "",
    "alt_prompt": "",
    "batch_size": 1,
    "repeat_generation": 1,
    "seed": 1234,
    "image_mode": 0,
    "multi_prompts_gen_type": "PW",
    "image_prompt_type": "",
    "settings_version": 2.79,
    "model_type": MODEL,
    "num_inference_steps": 8,
    "video_length": 121,
}

# first entry = warmup (pays model load, excluded)
TASKS = [
    ("warmup (excluded)", "832x480"),
    ("832x480, 8st", "832x480"),
    ("1280x704, 8st", "1280x704"),
]

TASK_START_RE = re.compile(r"^\[Task (\d+)/(\d+)\]")
QUEUE_DONE_RE = re.compile(r"^Queue completed:\s*(\d+)/(\d+)\s*tasks")


def build_queue():
    q = [dict(COMMON, resolution=res) for _, res in TASKS]
    path = os.path.join(OUT_DIR, "ab_queue_ltx25.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(q, f, indent=2, ensure_ascii=False)
    return path


def run_once(attention, queue_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    cmd = [PY, "wgp.py", "--process", queue_path,
           "--output-dir", out_dir, "--attention", attention]
    # platform.machine() reads PROCESSOR_ARCHITECTURE; if the launching shell kept it
    # empty (Git Bash / task schedulers), mmgp's allocator DLL is not found and WanGP
    # silently falls back to PyTorch's allocator. Pin it so the run matches a normal one.
    env = dict(os.environ)
    env.setdefault("PROCESSOR_ARCHITECTURE", "AMD64")
    print(f"\n=== attention={attention} ===", flush=True)
    print("cmd:", " ".join(cmd), flush=True)

    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", bufsize=1,
                            env=env)
    results = []
    start = None
    idx = -1
    for line in proc.stdout:
        line = line.rstrip()
        if line.startswith("[Task") or "Queue completed" in line or "attention" in line.lower():
            print(line, flush=True)
        m = TASK_START_RE.match(line)
        if m:
            if start is not None and 0 <= idx < len(results):
                results[idx]["duration_s"] = round(time.time() - start, 1)
            idx = int(m.group(1)) - 1
            start = time.time()
            while len(results) <= idx:
                results.append({"name": f"task{len(results)+1}", "duration_s": None})
            if idx < len(TASKS):
                results[idx]["name"] = TASKS[idx][0]
                results[idx]["resolution"] = TASKS[idx][1]
        d = QUEUE_DONE_RE.match(line)
        if d:
            print(f"  queue completed: {d.group(1)}/{d.group(2)}", flush=True)
    proc.wait()
    if start is not None and 0 <= idx < len(results):
        results[idx]["duration_s"] = round(time.time() - start, 1)
    print(f"  exit={proc.returncode} wall={round(time.time()-t0,1)}s", flush=True)
    return results, proc.returncode


def main():
    queue_path = build_queue()
    runs = {}
    for attn in ("sage2", "sage3"):
        out = os.path.join(OUT_DIR, f"out-{attn}")
        runs[attn], rc = run_once(attn, queue_path, out)
        runs[attn + "_rc"] = rc

    print("\n" + "=" * 74)
    print("A/B result — LTX-2.5 REDGraft 22B, 121 frames, 8 steps, seed 1234")
    print("=" * 74)
    print(f"{'task':20s} {'res':10s} {'sage2 s':>9s} {'sage3 s':>9s} {'sage3/sage2':>12s}")
    for i, (name, res) in enumerate(TASKS):
        if i == 0:
            continue
        a = runs["sage2"][i]["duration_s"] if i < len(runs["sage2"]) else None
        b = runs["sage3"][i]["duration_s"] if i < len(runs["sage3"]) else None
        ratio = f"{b/a:.3f}x" if (a and b) else "n/a"
        print(f"{name:20s} {res:10s} {str(a):>9s} {str(b):>9s} {ratio:>12s}")
    print(f"\nexit codes: sage2={runs['sage2_rc']} sage3={runs['sage3_rc']}")
    print("(<1.000x means sage3 was faster)")


if __name__ == "__main__":
    main()
