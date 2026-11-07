# WanGP Studio — Prompt Engineer

The Prompt Engineer node prepares image and video prompts from an idea and
optional reference image(s). It reuses the existing WanGP AI Analyze runtime,
not a separate LLM service.

## Using it
1. Open Studio → Workflow and add Prompt Engineer under AI.
2. Enter an idea in Inspector, or connect Text to the idea port.
3. Optionally connect Input Image to images (variadic input).
4. Choose Image, Video or Both and select one of WanGP's native AI model options.
5. Connect image_prompt to Generate Image.prompt and/or video_prompt to Generate Video.prompt.
6. Choose installed generation models, Save and Run workflow normally.

Both mode returns two distinct TEXT outputs from a single AI request. Image
and Video modes expose only their relevant output port. Reference images
are treated as initial frames for video prompts. Output validation rejects
empty or malformed dual prompts instead of passing them to the renderer.

On 12 GB VRAM prefer native 4B AI models and use WanGP offload controls
before launching a large image/video checkpoint. This feature does not
automatically install a huihui-ai model or select arbitrary HF checkpoints.

Limitations: Requires compatible WanFlow UI and WanGP AI runtime; full GPU
acceptance must be measured on the target computer.