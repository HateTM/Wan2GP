"""
Diagnose where LTX2.5 Pixel Upscaler x2 spends its time.

Reproduces the user's `redgraft` benchmark case that took 501.8s:
  model ltx2_25_22B_redgraft_nsfw, 832x480, 121 frames, 8 steps, spatial_upsampling=ltx25*2

Runs the queue through wgp.py --process and timestamps every stdout line that
carries phase/progress information, so the cost split between the base
generation, the upsampler windows and VAE phases becomes visible.

Usage (from the repo root):
    env_uv/Scripts/python.exe benchmarks/ab-sage3/ab_upscale.py
"""

import json
import os
import re
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
PY = os.path.join(REPO_ROOT, "env_uv", "Scripts", "python.exe")

MODEL = "ltx2_25_22B_redgraft_nsfw"
PROMPT = (
    "A cinematic drone shot flying over a coastal road at sunset, waves crashing "
    "on rocks below, warm golden light, smooth continuous camera movement."
)
COMMON = {
    "prompt": PROMPT, "negative_prompt": "", "alt_prompt": "",
    "batch_size": 1, "repeat_generation": 1, "seed": 1234, "image_mode": 0,
    "multi_prompts_gen_type": "PW", "image_prompt_type": "",
    "settings_version": 2.79, "model_type": MODEL,
    "num_inference_steps": 8, "video_length": 121,
}
TASKS = [
    ("warmup: 832x480 base, no upscale", {"resolution": "832x480"}),
    ("832x480 + LTX2.5 Pixel Upscaler x2", {"resolution": "832x480", "spatial_upsampling": "ltx25*2"}),
]

TASK_START_RE = re.compile(r"^\[Task (\d+)/(\d+)\]")
# progress lines look like: "  [ 3/8] Window 1 / 2 - Distilled Refinement | Phase ..."
PROGRESS_RE = re.compile(r"\[\s*(\d+)/(\d+)\]")


def build_queue():
    q = [dict(COMMON, **extra) for _, extra in TASKS]
    path = os.path.join(HERE, "upscale_queue.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(q, f, indent=2, ensure_ascii=False)
    return path


def main():
    queue = build_queue()
    out_dir = os.path.join(HERE, "out-upscale")
    os.makedirs(out_dir, exist_ok=True)
    cmd = [PY, "wgp.py", "--process", queue, "--output-dir", out_dir]
    env = dict(os.environ)
    env.setdefault("PROCESSOR_ARCHITECTURE", "AMD64")
    print("cmd:", " ".join(cmd), flush=True)

    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", bufsize=1, env=env)

    task = None
    task_t0 = None
    events = []          # (elapsed, kind, text)
    seen_phases = {}
    for raw in proc.stdout:
        line = raw.rstrip()
        el = time.time() - t0
        m = TASK_START_RE.match(line)
        if m:
            idx = int(m.group(1)) - 1
            task = TASKS[idx][0] if idx < len(TASKS) else f"task{idx+1}"
            task_t0 = el
            print(f"[{el:7.1f}s] === TASK {idx+1}: {task} ===", flush=True)
            continue
        if "upsampling complete" in line or "Queue completed" in line or "Sol-Attn" in line:
            print(f"[{el:7.1f}s] {line}", flush=True)
        # phase changes: capture the label after the last '-'
        pm = PROGRESS_RE.search(line)
        if pm:
            label = line.split("|")[-1].strip() if "|" in line else line.strip()
            label = re.sub(r"\[\s*\d+/\d+\]", "", label).strip()
            key = label
            if seen_phases.get(key) is None:
                seen_phases[key] = el
                print(f"[{el:7.1f}s]   phase start: {label}", flush=True)
            events.append((el, label))
    proc.wait()
    total = time.time() - t0

    print(f"\nexit={proc.returncode} total={total:.1f}s")
    print("\nphase -> cumulative seconds until next phase")
    # collapse consecutive identical labels
    seq = []
    for el, label in events:
        if seq and seq[-1][1] == label:
            seq[-1] = (el, label)
        else:
            seq.append((el, label))
    for i, (el, label) in enumerate(seq):
        nxt = seq[i + 1][0] if i + 1 < len(seq) else total
        print(f"  {el:7.1f}s .. {nxt:7.1f}s  ({(nxt-el):6.1f}s)  {label}")


if __name__ == "__main__":
    main()
