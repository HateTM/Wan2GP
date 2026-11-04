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
- Incremental media index: a rescan only re-lists the directories whose mtime changed (new/deleted/renamed children); a full reconcile runs on forced rescans and at least every 60 s, so in-place overwrites are picked up there. `GET /api/media/roots` reports the last scan (`mode`, visited/reused directories, duration).
- Bounded gallery memory: the browser keeps only a window of pages around the viewport (`KEEP_PAGES`), renders skeletons for pages being fetched and refetches evicted pages when scrolling back; selection is capped at 1000 ids. The 10k-file benchmark (`STUDIO_MEDIA_BENCH=1`) measures cold scan, incremental reuse, reconcile, query variants and backend RSS.
- Upload Center: drop/browse uploads run as a bounded-parallelism queue (2 concurrent), with per-file XHR progress, per-file failure reasons, retry, cancel and a gallery refresh once the queue drains.
- Real SendTo hand-off: Studio reads the target plugin's `sendto.json` manifest (the same contract the SendTo plugin uses), parks a one-shot hand-off id, and opens the WanGP UI with `?studio_sendto=<id>`. A hidden Studio control in the main Gradio UI receives the live session `state`, appends `{"path", "slot"}` to the manifest's `inbox_key`, and the injected JS selects the target tab so the plugin drains the frame into the chosen slot (Image Suite: Img2Img / MultiCanvas / Modify). No code is copied from the target plugin; without the bridge or the plugin the UI degrades to a copied path. Targets are filtered by the manifest's `accepts` kinds and the plugin's enabled state on both the UI and the API side.

The first frontend was deliberately a lightweight bootstrap; the later milestones replaced that scope. As of 1.3 the visual node canvas supports graph editing, workflow persistence and multi-node execution through `/api/workflow/*`, the Media Center is a real gallery browser (lightbox, upload, Worlds) with an incremental index, and Resources shows live RAM/VRAM telemetry. Image editing happens through SendTo into the enabled editor plugin (Image Suite) rather than a built-in editor. The Plugins view is a health board: every installed plugin is compared with its upstream repository (version, behind/ahead, local commits, dead remotes) without ever auto-updating a fork. The queue panel shows Studio-submitted jobs, not every task submitted from the native WanGP UI.

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
- POST /studio/api/media/{media_id}/sendto with {"plugin", "slot"} (parks a one-shot hand-off and returns a `/?studio_sendto=` URL; see below)
- GET /studio/api/sendto/targets (SendTo-capable plugins from their `sendto.json` manifests, plus bridge availability)
- GET /studio/api/sendto/{handoff_id} (hand-off status: pending / consumed / expired)
- DELETE /studio/api/media/{media_id}?confirm=true (removes the file and its .json sidecar)
- GET /studio/api/environment (capability registry: plugin states, integration levels, licenses)
- GET /studio/api/plugins/health[?wait=1] (installed-vs-upstream state per plugin: version, fork/divergence flags, local commits, remote reachability; `wait=1` also contacts remotes once)
- POST /studio/api/plugins/health/refresh (background upstream scan, cooldown-limited)
- GET /studio/api/workflow/status | /catalog | /workflows[/{slug}] (GET, PUT, DELETE)
- POST /studio/api/workflow/validate (normalize + cycle/topology check)
- POST /studio/api/workflow/runs with {graph, inputs}; GET /runs/{run_id}; GET /runs/{run_id}/events (SSE); POST /runs/{run_id}/cancel

## Vendored canvas assets

`web/assets/canvas.{html,css,js}` are the WanFlow UI editor assets (Apache-2.0, © Javier) vendored unchanged to serve the Studio workflow canvas through `register_web_app`; the license text is kept in `web/assets/WANFLOW-LICENSE.txt`. The Studio-side host (`web/assets/workflow.js`) replaces WanFlow's Gradio hidden-button bridge with the `/studio/api/workflow/*` facade.

The vendored `canvas.js` carries one documented Studio patch: it answers host `get_graph` requests with the current graph (`WAN2GP_WORKFLOWS_V2` `graph` reply) and ignores messages that do not come from `window.parent`. Re-vendoring a newer WanFlow release must re-apply this patch (see `tests/test_frontend_static.py`).

The full WanFlow UI plugin itself is vendored at `plugins/wan2gp-wanflow-ui` — the reconciled fork (0.2.0; see `RECONCILIATION.md` there): a verified superset of upstream with result cache/resume, resource preflight, the Compare A/B node and the FFmpeg 9 fix. Its tests run in CI by default; the `studio-integration` job stays opt-in for checking Studio against an alternate WanFlow version via the `WANFLOW_UI_REPO` variable. Never update that folder with `git pull` — it carries local git history; re-run the content-level reconciliation instead. `tests/test_vendored_sync.py` fails loudly when the fork and the vendored snapshot drift apart in either direction.

## Testing

Run the suites with the repo venv:

- `env_uv/Scripts/python.exe -m pytest plugins/wan2gp_studio/tests -q`
- `env_uv/Scripts/python.exe -m pytest plugins/plugin_manager/tests -q` (version-compare and update fork-guard regressions for `shared/utils/plugins.py`)
- `env_uv/Scripts/python.exe -m pytest plugins/wan2gp-wanflow-ui/tests -q` (the vendored WanFlow UI fork against current WanGP). CI runs the CPU-safe subset: the graph-runner modules import mmgp, which needs a CUDA-enabled torch, so `tests/cuda_gate.py` skips them only when CUDA is genuinely unavailable - with CUDA present a broken import fails the run instead of hiding behind a skip. A GPU workstation runs the full suite and remains the acceptance gate.
- `python -m playwright install chromium && python -m pytest plugins/wan2gp_studio/e2e -q` (browser tests in `e2e/`: a real uvicorn server + headless Chromium assert the gallery page-store bounds, scroll-back refetch, upload queue and filters). The separate `Studio E2E` workflow runs them on every Studio change; `WANFLOW_REQUIRE_CUDA=1 python -m pytest plugins/wan2gp-wanflow-ui/tests -q` is the strict GPU acceptance gate.

- The core CI job installs pinned test dependencies, including `diffusers==0.36.0` — `shared.utils` imports it at package init, so a missing diffusers fails at collection.
- Tests that need the optional WanFlow UI plugin skip when it is absent. The `studio-integration` job clones the plugin from the repository variables `WANFLOW_UI_REPO` (git URL) and `WANFLOW_UI_REF` (default `main`), sets `WANFLOW_UI_REQUIRED=1`, and then a missing WanFlow import fails the run instead of silently skipping. Set both variables under Settings → Secrets and variables → Actions → Variables to enable it.

## Documentation

- [User guide](docs/USER_GUIDE.md) — install/upgrade, views, gallery, workflow, resources.
- [Integration and compatibility](docs/INTEGRATION.md) — L1/L2/L3 matrix, capability registry, degradation rules.
- [Troubleshooting](docs/TROUBLESHOOTING.md) — 404/401/503/422, NVML, empty gallery, known issues.

## WanGP attribution

WanGP Studio is an integration built on WanGP. It does not replace or redistribute the WanGP generation engine. Keep the WanGP attribution and applicable license notices intact.
