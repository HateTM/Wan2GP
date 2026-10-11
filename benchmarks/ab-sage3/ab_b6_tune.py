"""
beta6 W4A8 tuning in one warm WanGP API session: DMAD/PDMD LoRA weights at 4 (and 2) steps,
Spectrum and First Block Cache at 8 steps. One task per variant and prompt, first task = warmup.

Usage (repo root):
    env_uv/Scripts/python.exe benchmarks/ab-sage3/ab_b6_tune.py [--only base8 d10 ...] [--prompts A B]
Results: benchmarks/ab-sage3/b6_tune_results.json (written after every task), videos in out_b6_tune/.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)
os.environ.setdefault("PROCESSOR_ARCHITECTURE", "AMD64")

MODEL = "minimax_h3_10eros_max_b6_fl2va"
DMAD = "minimax_h3_DMAD_4step_full_lora_avg_rank_39_bf16.safetensors"
PDMD4 = "minimax_h3_pdmd_4step_lora_avg_rank_57_bf16.safetensors"
PDMD2 = "minimax_h3_pdmd_2step_lora_avg_rank_38_bf16.safetensors"

PROMPTS = {
    "A": "A cinematic drone shot flying over a coastal road at sunset, waves crashing on rocks below.",
    "B": "Close-up of a young woman with curly red hair sitting in a busy cafe, she looks into the camera, smiles and says: \"I didn't expect you to come back so soon.\" Soft window light, shallow depth of field, cafe chatter in the background.",
}


def lora(*pairs):
    return {"activated_loras": [name for name, _ in pairs], "loras_multipliers": " ".join(str(w) for _, w in pairs)}


VARIANTS = {
    "base8": {"num_inference_steps": 8},
    "d10": {"num_inference_steps": 4, **lora((DMAD, 1.0))},
    "d10p05": {"num_inference_steps": 4, **lora((DMAD, 1.0), (PDMD4, 0.5))},
    "d075p025": {"num_inference_steps": 4, **lora((DMAD, 0.75), (PDMD4, 0.25))},
    "d05p05": {"num_inference_steps": 4, **lora((DMAD, 0.5), (PDMD4, 0.5))},
    "d075": {"num_inference_steps": 4, **lora((DMAD, 0.75))},
    "p10": {"num_inference_steps": 4, **lora((PDMD4, 1.0))},
    "p2s10": {"num_inference_steps": 2, **lora((PDMD2, 1.0))},
    "spec0": {"num_inference_steps": 8, "skip_steps_cache_type": "spectrum", "skip_steps_start_step_perc": 0},
    "spec25": {"num_inference_steps": 8, "skip_steps_cache_type": "spectrum", "skip_steps_start_step_perc": 25},
    "fbc06": {"num_inference_steps": 8, "skip_steps_cache_type": "first_block", "skip_steps_multiplier": 0.06},
    "fbc08": {"num_inference_steps": 8, "skip_steps_cache_type": "first_block", "skip_steps_multiplier": 0.08},
    "fbc10": {"num_inference_steps": 8, "skip_steps_cache_type": "first_block", "skip_steps_multiplier": 0.10},
}


def task(prompt_key, overrides):
    t = {
        "model_type": MODEL, "prompt": PROMPTS[prompt_key], "negative_prompt": "", "seed": 1234,
        "image_mode": 0, "image_prompt_type": "", "batch_size": 1, "repeat_generation": 1,
        "video_length": 41, "resolution": "832x480", "sample_solver": "res_multistep",
        "guidance_scale": 1.0, "guidance_phases": 1, "flow_shift": 10.0, "override_attention": "",
        "activated_loras": [], "loras_multipliers": "", "skip_steps_cache_type": "",
    }
    t.update(overrides)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="+", default=list(VARIANTS))
    ap.add_argument("--prompts", nargs="+", default=list(PROMPTS))
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    out_dir = os.path.join(HERE, "out_b6_tune" + (f"_{args.tag}" if args.tag else ""))
    res_path = os.path.join(HERE, "b6_tune_results" + (f"_{args.tag}" if args.tag else "") + ".json")
    os.makedirs(out_dir, exist_ok=True)

    from shared.api import init
    session = init(output_dir=out_dir, console_output=True)

    jobs = [("warmup", "A", VARIANTS["base8"])] + [(v, p, VARIANTS[v]) for p in args.prompts for v in args.only]
    results = []
    for name, p, overrides in jobs:
        print(f"\n##### {name} / prompt {p}", flush=True)
        start = time.time()
        r = session.run_task(task(p, overrides))
        dur = round(time.time() - start, 1)
        files = list(r.generated_files)
        errors = [str(e) for e in r.errors]
        size = os.path.getsize(files[0]) if files and os.path.exists(files[0]) else 0
        print(f"##### {name}/{p}: {dur}s files={files} errors={errors}", flush=True)
        results.append({"variant": name, "prompt": p, "seconds": dur, "file": files[0] if files else None,
                        "size_mb": round(size / 1e6, 2), "errors": errors, "settings": overrides})
        with open(res_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=True)


if __name__ == "__main__":
    main()
