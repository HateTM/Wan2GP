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

The web app is registered through WAN2GPPlugin.register_web_app() and is served by the existing WanGP server behind its authentication. The plugin metadata declares WanGP 18.84 as its minimum supported version, matching the API surface used by this implementation.

## Scope (v1.0)

v1.0 covers the Dashboard, Workflow (node canvas with save/run/cancel and import/export), Media Center (gallery, upload, Worlds), Models (availability, presets, LoRA inventory), Resources (read-only telemetry) and Settings (read-only diagnostics). The bullets below describe the original v0.1 bootstrap that the later milestones extended.

- Dynamic model catalogue with basic search and output-type filters.
- Per-model inspection: definition, metadata, capability schema, local model-file availability, native defaults, presets/profiles and installed LoRA inventory.
- Loading a native WanGP preset/profile into the full settings editor.
- Editable full settings JSON with prompt shortcut.
- Single-task submission through the native WanGP queue.
- Job progress, status, completion, errors and cancellation through the existing API.
- SSE progress stream with keep-alive comments and a bounded in-memory job history (maximum 50 queued/running Studio jobs).
- Media Center discovery API: the four WanGP output roots, dedicated workspace folders and optional workflow outputs, with embedded metadata, World manifest summaries and thumbnails from the shared Deepy engine.

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
- GET /studio/api/media?kind=&q=&sort=&limit=50&offset=0 (indexes the WanGP output roots)
- GET /studio/api/media/roots (scan stats and the roots being indexed)
- GET /studio/api/media/{media_id} (file facts and embedded metadata; Worlds add a manifest summary)
- GET /studio/api/media/{media_id}/thumbnail (JPEG from the shared Deepy thumbnail engine)
- GET /studio/api/media/{media_id}/file (streams the original file for previews and downloads)
- POST /studio/api/media/upload (multipart `file`; copies into the matching WanGP output root)
- DELETE /studio/api/media/{media_id}?confirm=true (removes the file and its .json sidecar)
- GET /studio/api/environment (capability registry: plugin states, integration levels, licenses)
- GET /studio/api/workflow/status | /catalog | /workflows[/{slug}] (GET, PUT, DELETE)
- POST /studio/api/workflow/validate (normalize + cycle/topology check)
- POST /studio/api/workflow/runs with {graph, inputs}; GET /runs/{run_id}; GET /runs/{run_id}/events (SSE); POST /runs/{run_id}/cancel

## Vendored canvas assets

`web/assets/canvas.{html,css,js}` are the WanFlow UI editor assets (Apache-2.0, © Javier) vendored unchanged to serve the Studio workflow canvas through `register_web_app`; the license text is kept in `web/assets/WANFLOW-LICENSE.txt`. The Studio-side host (`web/assets/workflow.js`) replaces WanFlow's Gradio hidden-button bridge with the `/studio/api/workflow/*` facade.

The vendored `canvas.js` carries one documented Studio patch: it answers host `get_graph` requests with the current graph (`WAN2GP_WORKFLOWS_V2` `graph` reply) and ignores messages that do not come from `window.parent`. Re-vendoring a newer WanFlow release must re-apply this patch (see `tests/test_frontend_static.py`).

## Testing

Run the suite with the repo venv: `env_uv/Scripts/python.exe -m pytest plugins/wan2gp_studio/tests -q`.

- The core CI job installs pinned test dependencies, including `diffusers==0.36.0` — `shared.utils` imports it at package init, so a missing diffusers fails at collection.
- Tests that need the optional WanFlow UI plugin skip when it is absent. The `studio-integration` job clones the plugin from the repository variables `WANFLOW_UI_REPO` (git URL) and `WANFLOW_UI_REF` (default `main`), sets `WANFLOW_UI_REQUIRED=1`, and then a missing WanFlow import fails the run instead of silently skipping. Set both variables under Settings → Secrets and variables → Actions → Variables to enable it.

## Documentation

- [User guide](docs/USER_GUIDE.md) — install/upgrade, views, gallery, workflow, resources.
- [Integration and compatibility](docs/INTEGRATION.md) — L1/L2/L3 matrix, capability registry, degradation rules.
- [Troubleshooting](docs/TROUBLESHOOTING.md) — 404/401/503/422, NVML, empty gallery, known issues.

## WanGP attribution

WanGP Studio is an integration built on WanGP. It does not replace or redistribute the WanGP generation engine. Keep the WanGP attribution and applicable license notices intact.
