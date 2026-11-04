# WanGP Studio — Troubleshooting

## `/studio/` returns 404

- The plugin is not enabled: check the Plugin Manager (`wan2gp_studio` in `enabled_plugins`).
- WanGP was not restarted after enabling: the web app is mounted at startup.
- Startup log should contain `Loaded App: WanGP Studio (from wan2gp_studio)`.

## 401 / 403 responses

- `401 {"detail": "Sign in to WanGP."}` — WanGP runs with `--auth`; sign in at `/auth/login`.
- `403` on POST — the request came from another origin. Studio relies on WanGP's same-origin check; use the page served from the same host and port.
- Without `--auth` the whole app is open (WanGP behaviour); Studio adds no separate login.

## Workflow section says `not_installed`

`wan2gp-wanflow-ui` is not installed or its folder was renamed. Install it from the Plugin Manager and restart. Everything except the workflow canvas keeps working: `/api/workflow/*` answers `503` with a structured detail, `/api/workflow/status` reports the reason.

## `422` on workflow import

ComfyUI **API** JSON (`{"1": {"class_type": …}}`) imports as opaque `comfyui_node` nodes — preserved and exportable, but not executable in WanGP yet. ComfyUI **UI-format** JSON is rejected with `422` and `report.reason = "ui-format"`. Export the ComfyUI API (prompt) JSON instead.

The payload was detected as ComfyUI JSON (`links` or `class_type` structure). ComfyUI import is not implemented yet; export the graph as `wan2gp-wanflow-ui` JSON instead. The response contains `{"report": {"format": "comfyui", "supported": false}}`.

## Workflow run fails immediately

- Open the run snapshot (`GET /studio/api/workflow/runs/{id}`) — `errors` carries the exception text.
- `WorkflowUnavailable` means the adapter could not import the plugin modules; reinstall `wan2gp-wanflow-ui`.
- After a WanGP update, private adapter points (`_ui_local`, `_process_inline_queue`, `server_config`) may have moved. Re-run `python -m pytest plugins/wan2gp_studio/tests` and check `workflow_compat.py` first.

## Workflow cancel leaves a node "cancelled"

Expected: the running node is marked `cancelled` and the run status becomes `cancelled`. Nodes that already finished keep `done`.

## Resources shows `unavailable`

- GPU card: NVML is unavailable (`pynvml` missing, driver without NVML, or a non-NVIDIA GPU). Studio reports the source honestly instead of zeros.
- `fan —` on laptops is normal: many mobile GPUs expose no fan reading.
- CPU may show `0.0%` on the very first sample; psutil needs one interval between reads.

## Gallery is empty

- Check **Settings → Media roots**: the four output paths from `wgp_config.json` (`save_path`, `image_save_path`, `audio_save_path`, `mesh_save_path`) plus dedicated workspace folders and optional `workflow_outputs`.
- Press **Rescan**. The index rescans at most every 3 seconds.
- `.wgpworld` files exist only next to their generated `.mp4`; files uploaded through Studio are images/videos/audio only.

## Upload rejected

- `400 Unsupported media type` — only image/video/audio extensions are accepted.
- `413 File is larger than 512 MB` — the limit is `MEDIA_UPLOAD_MAX_BYTES` in `plugin.py`.

## Jobs SSE replays history

By design: Studio streams from a cursor (`?cursor=` or `Last-Event-ID`) and keeps bounded histories (jobs: 100 events per job; workflow runs: 400). Pass the last event id to resume; a fresh connection without a cursor replays the bounded buffer and then ends.

## Known third-party issue: krea2 plugin error on startup

`[PluginManager] ERROR in post_ui_setup for wan2gp-krea2-identity-edit` comes from that plugin (`custom_settings_visibility_trigger` missing). WanGP isolates plugin failures; Studio is unaffected. Report upstream or disable the plugin.

## Nothing leaves the machine

Studio makes no outbound network calls. It reads local files, talks to the local WanGP runtime and renders local media. Uploads write into the configured output folders.
