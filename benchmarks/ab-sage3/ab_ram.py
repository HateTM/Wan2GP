"""
RAM-allocator / reserved-RAM A/B with Nsight Systems (cuda-profiling workflow).

Per variant:
  1. wall-clock per task, N repeats, median (queue ab_queue_ltx25.json, first task = warmup)
  2. one `nsys profile --trace=cuda,nvtx` run of the 41-frame queue (nsys_queue.json),
     then SQLite analysis: GPU busy/idle share over the kernel span, H2D volume/time.

Usage (repo root):
    env_uv/Scripts/python.exe benchmarks/ab-sage3/ab_ram.py --variants ram-mmgp ram-default perc03 --repeat 3
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
PY = os.path.join(REPO_ROOT, "env_uv", "Scripts", "python.exe")
NSYS = r"C:\Program Files\NVIDIA Corporation\Nsight Systems 2026.3.2\target-windows-x64\nsys.exe"
TIMING_QUEUE = os.path.join(HERE, "ab_queue_ltx25.json")
NSYS_QUEUE = os.path.join(HERE, "nsys_queue.json")
NAMES = ["warmup (excluded)", "832x480, 8st", "1280x704, 8st"]
TASK_RE = re.compile(r"^\[Task (\d+)/(\d+)\]")

VARIANTS = {
    "ram-mmgp": ["--ram-allocator", "mmgp"],
    "ram-default": ["--ram-allocator", "default"],
    "perc03": ["--ram-allocator", "mmgp", "--perc-reserved-mem-max", "0.3"],
    "perc05": ["--ram-allocator", "mmgp", "--perc-reserved-mem-max", "0.5"],
}


def free_gb():
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
                         capture_output=True, text=True)
    try:
        return int(out.stdout.strip()) / 1024 / 1024
    except ValueError:
        return -1.0


def base_env():
    env = dict(os.environ)
    env.setdefault("PROCESSOR_ARCHITECTURE", "AMD64")  # else mmgp allocators silently fall back
    return env


def run_timed(cmd, env):
    proc = subprocess.Popen(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", bufsize=1, env=env)
    durs, start, idx, ram_line = [], None, -1, ""
    for raw in proc.stdout:
        line = raw.rstrip()
        if "[RAM]" in line:
            ram_line = line[:120]
        m = TASK_RE.match(line)
        if m:
            if start is not None:
                durs[idx] = round(time.time() - start, 1)
            idx = int(m.group(1)) - 1
            start = time.time()
            durs.append(None)
            print(line, flush=True)
    proc.wait()
    if start is not None:
        durs[idx] = round(time.time() - start, 1)
    return durs, proc.returncode, ram_line


def nsys_analyse(sqlite_path):
    con = sqlite3.connect(sqlite_path)
    k = con.execute("SELECT start, end FROM CUPTI_ACTIVITY_KIND_KERNEL").fetchall()
    m = con.execute("SELECT start, end, bytes, copyKind FROM CUPTI_ACTIVITY_KIND_MEMCPY").fetchall()
    con.close()
    if not k:
        return {}
    t0, t1 = min(s for s, _ in k), max(e for _, e in k)
    iv = sorted([(s, e) for s, e in k] + [(s, e) for s, e, _, _ in m])
    busy, cur_s, cur_e = 0, iv[0][0], iv[0][1]
    for s, e in iv[1:]:
        if s > cur_e:
            busy += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    busy += cur_e - cur_s
    h2d = [(s, e, b) for s, e, b, kind in m if kind == 1]
    span = t1 - t0
    return {
        "span_s": round(span / 1e9, 1),
        "busy_pct": round(100 * busy / span, 1),
        "idle_pct": round(100 * (1 - busy / span), 1),
        "kernel_s": round(sum(e - s for s, e in k) / 1e9, 2),
        "h2d_gb": round(sum(b for _, _, b in h2d) / 1e9, 1),
        "h2d_s": round(sum(e - s for s, e, _ in h2d) / 1e9, 2),
        "kernels": len(k),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="+", default=["ram-mmgp", "ram-default"])
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--no-nsys", action="store_true")
    args = ap.parse_args()
    env = base_env()
    report = {}
    for v in args.variants:
        extra = VARIANTS[v]
        out = os.path.join(HERE, "out-ram", v)
        os.makedirs(out, exist_ok=True)
        print(f"\n##### {v}: {extra} | free RAM {free_gb():.1f} GB", flush=True)
        per_task = {}
        ram_line = ""
        for rep in range(args.repeat):
            cmd = [PY, "wgp.py", "--process", TIMING_QUEUE, "--output-dir", out] + extra
            print(f"--- run {rep+1}/{args.repeat} (free RAM {free_gb():.1f} GB)", flush=True)
            durs, rc, ram_line = run_timed(cmd, env)
            print(f"    exit={rc} {durs}", flush=True)
            print(f"    {ram_line or '[RAM] line NOT found in log: allocator state unknown'}", flush=True)
            for i, d in enumerate(durs):
                if i > 0 and d is not None:
                    per_task.setdefault(NAMES[i], []).append(d)
        stats = {n: {"median": sorted(t)[len(t) // 2], "runs": t} for n, t in per_task.items()}
        entry = {"timing": stats, "ram_log": ram_line}
        if not args.no_nsys:
            rep_path = os.path.join(HERE, f"nsys_{v}")
            cmd = [NSYS, "profile", "--trace=cuda,nvtx", "--force-overwrite=true", "-o", rep_path,
                   PY, "wgp.py", "--process", NSYS_QUEUE, "--output-dir", os.path.join(out, "nsys")] + extra
            print(f"--- nsys: {' '.join(cmd[:4])} ...", flush=True)
            subprocess.run(cmd, cwd=REPO_ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run([NSYS, "export", "--type=sqlite", "--force-overwrite=true", "-o", rep_path + ".sqlite",
                            rep_path + ".nsys-rep"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            entry["nsys"] = nsys_analyse(rep_path + ".sqlite")
            print("    nsys:", entry["nsys"], flush=True)
        report[v] = entry
        with open(os.path.join(HERE, "ab_ram_results.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=True)
    print("\n" + "=" * 70)
    for v, e in report.items():
        t = {n: s["median"] for n, s in e["timing"].items()}
        print(v, t, e.get("nsys", {}).get("idle_pct"), "% idle")


if __name__ == "__main__":
    main()
