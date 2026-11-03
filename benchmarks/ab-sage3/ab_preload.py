"""
Measure per-task wall time of a queue with extra wgp.py arguments.

Reuses benchmarks/ab-sage3/ab_queue_ltx25.json (warmup, 832x480, 1280x704).
Times each task from the driver process via the "[Task i/N]" lines; the first
task is a warmup that pays the model load and is excluded from comparisons.

Usage (from the repo root):
    env_uv/Scripts/python.exe benchmarks/ab-sage3/ab_preload.py --preload 4000
    env_uv/Scripts/python.exe benchmarks/ab-sage3/ab_preload.py --profile 2
"""

import argparse
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
PY = os.path.join(REPO_ROOT, "env_uv", "Scripts", "python.exe")
QUEUE = os.path.join(HERE, "ab_queue_ltx25.json")

TASK_START_RE = re.compile(r"^\[Task (\d+)/(\d+)\]")
QUEUE_DONE_RE = re.compile(r"^Queue completed:\s*(\d+)/(\d+)\s*tasks")
NAMES = ["warmup (excluded)", "832x480, 8st", "1280x704, 8st"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preload", default="")
    ap.add_argument("--profile", default="")
    ap.add_argument("--compile", action="store_true")
    ap.add_argument("--vram-safety-coefficient", default="")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    extra = []
    label_parts = []
    if args.preload:
        extra += ["--preload", args.preload]
        label_parts.append(f"preload={args.preload}MB")
    if args.profile:
        extra += ["--profile", args.profile]
        label_parts.append(f"profile={args.profile}")
    if args.compile:
        extra += ["--compile"]
        label_parts.append("compile")
    if args.vram_safety_coefficient:
        extra += ["--vram-safety-coefficient", args.vram_safety_coefficient]
        label_parts.append(f"vsc={args.vram_safety_coefficient}")
    label = args.label or ("+".join(label_parts) or "baseline")

    out_dir = os.path.join(HERE, "out-preload", label.replace("=", "").replace("+", "_"))
    os.makedirs(out_dir, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("PROCESSOR_ARCHITECTURE", "AMD64")

    per_task = {}
    for rep in range(args.repeat):
        cmd = [PY, "wgp.py", "--process", QUEUE, "--output-dir", out_dir] + extra
        print(f"\n=== {label} [run {rep+1}/{args.repeat}] ===\ncmd: {' '.join(cmd)}", flush=True)
        results = one_run(cmd, env)
        for i, name in enumerate(NAMES):
            if i == 0:
                continue
            if i < len(results) and results[i]["duration_s"] is not None:
                per_task.setdefault(name, []).append(results[i]["duration_s"])

    print(f"\n--- {label} (repeat={args.repeat}) ---")
    stats = {}
    for name, times in per_task.items():
        times_sorted = sorted(times)
        med = times_sorted[len(times_sorted) // 2]
        stats[name] = med
        print(f"{name:20s} median={med:6.1f}s  runs={times}")
    return stats


def one_run(cmd, env):
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", bufsize=1, env=env)
    results, start, idx = [], None, -1
    for line in proc.stdout:
        line = line.rstrip()
        if line.startswith("[Task") or "Queue completed" in line:
            print(line, flush=True)
        m = TASK_START_RE.match(line)
        if m:
            if start is not None and 0 <= idx < len(results):
                results[idx]["duration_s"] = round(time.time() - start, 1)
            idx = int(m.group(1)) - 1
            start = time.time()
            while len(results) <= idx:
                results.append({"duration_s": None})
        d = QUEUE_DONE_RE.match(line)
        if d:
            print(f"  queue completed: {d.group(1)}/{d.group(2)}", flush=True)
    proc.wait()
    if start is not None and 0 <= idx < len(results):
        results[idx]["duration_s"] = round(time.time() - start, 1)
    print(f"  exit={proc.returncode} wall={round(time.time()-t0,1)}s", flush=True)
    return results


if __name__ == "__main__":
    main()