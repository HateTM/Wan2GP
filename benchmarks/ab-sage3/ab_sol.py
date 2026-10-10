"""
A/B: default attention (sage2) vs Sol-Attn override on MiniMax H3.

Uses the exact settings of benchmarks/run-full/bench_queue_h3.json (the user's
own H3 benchmark: minimax_h3_10eros_max_b5_fl2va, 832x480, 124 frames, 8 steps,
res_multistep, guidance 1, flow_shift 12) and only changes per-task
`override_attention`: "" (baseline) vs "sol".

Sol-Attn is a per-task override resolved in wgp.py; on H3 the bundled Triton
kernels engage for sequences >= 8192 tokens (models/minimax_h3/sol_attention.py).
The first task is a warmup that pays the model load and is excluded.

Usage (from the repo root):
    env_uv/Scripts/python.exe benchmarks/ab-sage3/ab_sol.py
"""

import json
import os
import re
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
PY = os.path.join(REPO_ROOT, "env_uv", "Scripts", "python.exe")
SOURCE_QUEUE = os.path.join(REPO_ROOT, "benchmarks", "run-full", "bench_queue_h3.json")

TASK_START_RE = re.compile(r"^\[Task (\d+)/(\d+)\]")
QUEUE_DONE_RE = re.compile(r"^Queue completed:\s*(\d+)/(\d+)\s*tasks")


def build_queues():
    with open(SOURCE_QUEUE, encoding="utf-8") as f:
        tasks = json.load(f)
    # warmup + baseline = the two 124-frame 8-step entries of the user's queue
    picked = tasks[:2]
    names = ["warmup (excluded)", "832x480, 124f, 8st, res_multistep"]
    queues = {}
    for mode in ("baseline", "sol"):
        q = []
        for t in picked:
            t = dict(t)
            t["override_attention"] = "" if mode == "baseline" else "sol"
            q.append(t)
        path = os.path.join(HERE, f"h3_queue_{mode}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(q, f, indent=2, ensure_ascii=False)
        queues[mode] = path
    return queues, names


def run_once(label, queue_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    cmd = [PY, "wgp.py", "--process", queue_path, "--output-dir", out_dir]
    env = dict(os.environ)
    env.setdefault("PROCESSOR_ARCHITECTURE", "AMD64")  # mmgp allocator needs it
    print(f"\n=== {label} ===\ncmd: {' '.join(cmd)}", flush=True)

    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", bufsize=1, env=env)
    results, start, idx = [], None, -1
    sol_seen = False
    for line in proc.stdout:
        line = line.rstrip()
        if "Sol-Attn" in line:
            sol_seen = True
            print("  >>", line, flush=True)
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
    print(f"  exit={proc.returncode} wall={round(time.time()-t0,1)}s sol_kernels_seen={sol_seen}", flush=True)
    return results, proc.returncode, sol_seen


def main():
    queues, names = build_queues()
    runs = {}
    for mode in ("baseline", "sol"):
        out = os.path.join(HERE, f"out-h3-{mode}")
        runs[mode] = run_once(f"H3 attention={mode}", queues[mode], out)

    print("\n" + "=" * 72)
    print("H3 A/B — MiniMax H3 10Eros FL2VA, 832x480, 124 frames, 8 steps")
    print("=" * 72)
    print(f"{'task':36s} {'baseline s':>11s} {'sol s':>9s} {'sol/base':>10s}")
    base_res, sol_res, _, _ = runs["baseline"][0], runs["sol"][0], None, None
    for i, name in enumerate(names):
        if i == 0:
            continue
        a = base_res[i]["duration_s"] if i < len(base_res) else None
        b = sol_res[i]["duration_s"] if i < len(sol_res) else None
        ratio = f"{b/a:.3f}x" if (a and b) else "n/a"
        print(f"{name:36s} {str(a):>11s} {str(b):>9s} {ratio:>10s}")
    print(f"\nsol kernels engaged: {runs['sol'][2]}")
    print(f"exit codes: baseline={runs['baseline'][1]} sol={runs['sol'][1]}")
    print("(<1.000x means sol was faster)")


if __name__ == "__main__":
    main()
