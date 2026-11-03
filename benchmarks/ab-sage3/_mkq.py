import json
common = {
    "prompt": "A cinematic drone shot flying over a coastal road at sunset, waves crashing on rocks below.",
    "negative_prompt": "", "alt_prompt": "", "batch_size": 1, "repeat_generation": 1,
    "seed": 1234, "image_mode": 0, "multi_prompts_gen_type": "PW", "image_prompt_type": "",
    "settings_version": 2.79, "model_type": "ltx2_25_22B_redgraft_nsfw",
    "num_inference_steps": 8, "video_length": 41, "resolution": "832x480",
}
json.dump([common], open(r"C:\Wan2GP\benchmarks\ab-sage3\nsys_queue.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("queue written: 41 frames, 8 steps, no upscale")
