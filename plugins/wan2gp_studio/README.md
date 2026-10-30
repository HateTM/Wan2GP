# WanGP Studio

WanGP Studio is a lightweight, full-screen plugin frontend for the existing WanGP runtime.

## Design constraints

- Does not call shared.api.init() and does not start a second generation runtime.
- Uses self.deepy.web_session() to submit work to the already-running WanGP WebUI queue.
- Keeps one lazy session per plugin app instance.
- Does not retain preview PIL images or MP4 preview bytes in backend memory.
- Uses static HTML, CSS and JavaScript in this bootstrap release; no second frontend server, bundler process, charting stack or animation runtime is required.
- Model metadata, defaults, schemas, presets and LoRAs are read from the installed WanGP API rather than a hard-coded model catalogue.

## Installation

1. Copy plugins/wan2gp_studio into the WanGP plugins directory.
2. In WanGP Plugin Manager, enable WanGP Studio.
3. Restart WanGP.
4. Open /studio/ on the same WanGP host.

The web app is registered through WAN2GPPlugin.register_web_app() and is served by the existing WanGP server behind its authentication.

## v0.1 scope

- Dynamic model catalogue with basic search and output-type filters.
- Per-model inspection: definition, metadata, capability schema, local model-file availability, native defaults, presets/profiles and installed LoRA inventory.
- Loading a native WanGP preset/profile into the full settings editor.
- Editable full settings JSON with prompt shortcut.
- Single-task submission through the native WanGP queue.
- Job progress, status, completion, errors and cancellation through the existing API.
- SSE progress stream with keep-alive comments and a bounded in-memory job history.

The first frontend is deliberately a lightweight bootstrap. The visual node canvas is currently a single generation-node workspace; graph editing, workflow persistence, multi-node execution, media editors, a real gallery browser and RAM/VRAM telemetry are follow-up milestones. The queue panel shows Studio-submitted jobs, not every task submitted from the native WanGP UI.

## API routes

- GET /studio/api/health
- GET /studio/api/models
- GET /studio/api/models/{model_type}
- GET /studio/api/models/{model_type}/settings?setting_id=... (loads a native preset/profile)
- GET /studio/api/jobs
- POST /studio/api/jobs with {"settings": {...WanGP settings...}}
- GET /studio/api/jobs/{job_id}
- GET /studio/api/jobs/{job_id}/events (SSE)
- POST /studio/api/jobs/{job_id}/cancel

## WanGP attribution

WanGP Studio is an integration built on WanGP. It does not replace or redistribute the WanGP generation engine. Keep the WanGP attribution and applicable license notices intact.
