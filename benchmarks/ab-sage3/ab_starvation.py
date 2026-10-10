"""
Disk/paging counters during a generation, via typeperf (reliable CSV output).

Question: the GPU is idle 64% of the generation window (nsys). Is the 15.86 GB
checkpoint being re-read from disk/pagefile because it does not stay resident in
32 GB of RAM next to the pinned staging buffers?

Counters of interest:
  \PhysicalDisk(_Total)\Disk Read Bytes/sec   - actual disk traffic
  \Memory\Pages Input/sec                     - hard faults (paging IN from disk)
  \Memory\Available MBytes                    - free RAM headroom
  \Paging File(_Total)\% Usage

Usage:
    env_uv/Scripts/python.exe benchmarks/ab-sage3/ab_starvation.py
"""

import csv
import os
import subprocess
import sys
import time
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
PY = os.path.join(REPO_ROOT, "env_uv", "Scripts", "python.exe")
QUEUE = os.path.join(HERE, "nsys_queue.json")      # 41 frames, 8 steps, no upscale
CSV_OUT = os.path.join(HERE, "counters.csv")

COUNTERS = [
    r"\PhysicalDisk(_Total)\Disk Read Bytes/sec",
    r"\PhysicalDisk(_Total)\Disk Reads/sec",
    r"\Memory\Pages Input/sec",
    r"\Memory\Available MBytes",
    r"\Paging File(_Total)\% Usage",
]
SECONDS = 170


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default=QUEUE)
    ap.add_argument("--label", default="ltx")
    args = ap.parse_args()

    env = dict(os.environ)
    env.setdefault("PROCESSOR_ARCHITECTURE", "AMD64")
    csv_out = os.path.join(HERE, f"counters_{args.label}.csv")

    # free RAM before
    def free_gb():
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
                             capture_output=True, text=True)
        try:
            return int(out.stdout.strip()) / 1024 / 1024
        except ValueError:
            return -1

    print(f"RAM free before: {free_gb():.1f} GB", flush=True)

    # 1) start typeperf (1 sample / 2 s)
    tp = subprocess.Popen(
        ["typeperf"] + COUNTERS + ["-si", "2", "-sc", str(SECONDS // 2),
                                   "-o", csv_out, "-y"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)

    # 2) run the generation
    cmd = [PY, "wgp.py", "--process", args.queue,
           "--output-dir", os.path.join(HERE, f"out-{args.label}")]
    print("cmd:", " ".join(cmd), flush=True)
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", bufsize=1, env=env)
    marks = []
    for raw in proc.stdout:
        line = raw.rstrip()
        if "Denoising" in line or line.startswith("[Task") or "Queue completed" in line:
            marks.append((time.time() - t0, line[:90]))
            if line.startswith("[Task") or "Queue completed" in line:
                print(f"[{time.time()-t0:7.1f}s] {line[:110]}", flush=True)
    proc.wait()
    gen_total = time.time() - t0
    tp.wait(timeout=30)
    print(f"\nexit={proc.returncode} generation wall={gen_total:.1f}s", flush=True)

    # generation (denoising) window in driver seconds
    gen_start = next((t for t, txt in marks if "Denoising" in txt), None)
    gen_end = next((t for t, txt in reversed(marks) if "Denoising" in txt or "Saving" in txt), gen_total)
    print(f"denoising window ≈ {gen_start:.0f}..{gen_end:.0f} s" if gen_start else "no marks")

    # 3) parse typeperf CSV
    if not os.path.exists(csv_out):
        print("no CSV produced"); return
    with open(csv_out, encoding="utf-8", errors="replace") as f:
        rows = list(csv.reader(f))
    if len(rows) < 2:
        print("empty CSV"); return
    header = rows[0]
    names = [h.strip('"').split("\\")[-1] for h in header]
    data = []
    for r in rows[1:]:
        if len(r) != len(header):
            continue
        data.append(r)

    def stat(idx):
        vals = []
        for r in data:
            try:
                vals.append(float(r[idx]))
            except ValueError:
                pass
        return vals

    print(f"\n{len(data)} samples over ~{len(data)*2}s")
    print(f"RAM free after : {free_gb():.1f} GB")
    print(f"{'counter':26s} {'avg':>12s} {'peak':>12s}")
    print("-" * 54)
    for i, name in enumerate(names):
        vals = stat(i)
        if not vals:
            continue
        if "Bytes" in name:
            mb = [v / 1024 / 1024 for v in vals]
            print(f"{name:26s} {sum(mb)/len(mb):11.1f}M {max(mb):11.1f}M  (MB/s)")
        else:
            print(f"{name:26s} {sum(vals)/len(vals):12.1f} {max(vals):12.1f}")


if __name__ == "__main__":
    main()
