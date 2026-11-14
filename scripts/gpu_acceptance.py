"""GPU acceptance for the shared WanGP API: generation, mid-denoise cancel,
VRAM release, model switching.

Scenario (defaults validated on RTX 5070 Ti 12 GB, 2026-11-15):
  run1  model A, 25 steps -- cancelled by a probe at the first denoise
        progress update; checks the graceful abort and the VRAM unload after it.
  run2  model B, short full run -- model switch right after a cancelled run.
  run3  model A, short full run -- switching back.

Prints one "[acceptance]" line per checkpoint and a final verdict line.
Exit code 0 when every checkpoint behaves as expected, 1 otherwise.
Worker console output is suppressed by the API (callback prints live in the
job's stream events); the checkpoints below print from the main thread and
always reach the terminal.

Usage: python scripts/gpu_acceptance.py [--model-a TYPE] [--model-b TYPE]
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def vram_used_gb():
    try:
        import torch
        free, total = torch.cuda.mem_get_info()
        return (total - free) / 2**30
    except Exception:
        return -1.0


class Probe:
    def __init__(self):
        self.job = None

    def on_progress(self, update):
        text = (str(getattr(update, "phase", "") or "") + " " + str(getattr(update, "status", "") or "")).lower()
        if "denois" in text and self.job is not None and not self.job.cancel_requested:
            self.job.cancel()

    def on_status(self, status):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-a", default="qwen_image_21_7B_noct_q_v4", help="model cancelled mid-denoise and reused in run3")
    parser.add_argument("--model-b", default="moss_image_dirty_moss", help="model switched to for run2")
    parser.add_argument("--steps-a", type=int, default=25)
    parser.add_argument("--steps-b", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=600, help="per-run timeout in seconds")
    parser.add_argument("--vram-drift-gb", type=float, default=0.3, help="tolerated VRAM growth over the baseline")
    args = parser.parse_args()

    from shared.api import init

    session = init(console_output=False)
    baseline = vram_used_gb()
    print(f"[acceptance] VRAM used before start: {baseline:.2f} GiB", flush=True)
    failures = []

    # --- Run 1: model A, cancel at the first denoise progress update ---
    settings = session.get_default_settings(args.model_a)
    settings.update(prompt="a red apple on a wooden table, studio light", negative_prompt="",
                    resolution="640x640", image_mode=1, batch_size=1, num_inference_steps=args.steps_a,
                    guidance_scale=4.0, seed=42)
    probe = Probe()
    job = session.submit_task(settings, callbacks=probe)
    probe.job = job
    t0 = time.time()
    while not job.done and time.time() - t0 < args.timeout:
        time.sleep(2)
    result = job.result()
    cancelled = job.cancel_requested and any("cancel" in str(e).lower() for e in result.errors)
    print(f"[acceptance] run1 done={job.done} cancel_requested={job.cancel_requested} "
          f"elapsed={time.time()-t0:.1f}s errors={[str(e) for e in result.errors]}", flush=True)
    if not job.done or not cancelled:
        failures.append("run1: expected a graceful mid-denoise cancellation")
    time.sleep(8)
    vram = vram_used_gb()
    print(f"[acceptance] VRAM after run1 cancel+unload: {vram:.2f} GiB", flush=True)
    if vram < 0 or vram > baseline + args.vram_drift_gb:
        failures.append(f"run1: VRAM {vram:.2f} GiB did not return near the {baseline:.2f} GiB baseline")

    # --- Run 2: switch to model B, short full run ---
    settings2 = session.get_default_settings(args.model_b)
    settings2.update(prompt="a small cottage in a pine forest, morning mist", resolution="640x640",
                     image_mode=1, batch_size=1, num_inference_steps=args.steps_b, guidance_scale=4.0, seed=7)
    res2 = session.run_task(settings2)
    print(f"[acceptance] run2 files={len(res2.generated_files)} errors={[str(e) for e in res2.errors]}", flush=True)
    if not res2.generated_files or res2.errors:
        failures.append("run2: expected a generated file without errors")
    time.sleep(5)
    vram = vram_used_gb()
    print(f"[acceptance] VRAM after run2: {vram:.2f} GiB", flush=True)
    if vram < 0 or vram > baseline + args.vram_drift_gb:
        failures.append(f"run2: VRAM {vram:.2f} GiB grew beyond the {baseline:.2f} GiB baseline")

    # --- Run 3: switch back to model A, full run ---
    settings3 = session.get_default_settings(args.model_a)
    settings3.update(prompt="a sailboat on a calm lake at sunset", resolution="640x640",
                     image_mode=1, batch_size=1, num_inference_steps=args.steps_b, guidance_scale=4.0, seed=9)
    res3 = session.run_task(settings3)
    print(f"[acceptance] run3 files={len(res3.generated_files)} errors={[str(e) for e in res3.errors]}", flush=True)
    if not res3.generated_files or res3.errors:
        failures.append("run3: expected a generated file without errors")
    time.sleep(5)
    vram = vram_used_gb()
    print(f"[acceptance] VRAM after run3: {vram:.2f} GiB", flush=True)
    if vram < 0 or vram > baseline + args.vram_drift_gb:
        failures.append(f"run3: VRAM {vram:.2f} GiB grew beyond the {baseline:.2f} GiB baseline")

    if failures:
        for failure in failures:
            print(f"[acceptance] FAIL {failure}", flush=True)
        return 1
    print("[acceptance] PASS", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
