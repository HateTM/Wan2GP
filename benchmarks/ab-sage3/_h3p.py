import json
t = {
    "prompt": "A cinematic drone shot flying over a coastal road at sunset, waves crashing on rocks below.",
    "negative_prompt": "", "alt_prompt": "", "batch_size": 1, "repeat_generation": 1,
    "seed": 1234, "image_mode": 0, "multi_prompts_gen_type": "PW", "image_prompt_type": "",
    "settings_version": 2.79, "model_type": "minimax_h3_10eros_max_b5_fl2va",
    "num_inference_steps": 8, "video_length": 41, "resolution": "832x480",
    "sample_solver": "res_multistep", "guidance_scale": 1.0, "guidance_phases": 1, "flow_shift": 12.0,
}
json.dump([t], open(r"C:\Wan2GP\benchmarks\ab-sage3\h3_phase_queue.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("ok")
