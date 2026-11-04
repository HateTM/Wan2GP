# WanGP Studio — Integration and Compatibility

Studio is an integration shell. It reaches optional plugins only through documented in-process APIs and degrades when they are missing.

## Integration levels

| Level | Meaning | Allowed when |
|---|---|---|
| **L1** | Deep link to the plugin's native WanGP tab. No code or API use. | Always |
| **L2** | In-process calls through the registry (`app.plugin_manager.get_all_plugins()`) or contract methods. No code copying. | The plugin has a license and a stable contract |
| **L3** | Vendoring code (copy/порт) into Studio. | The license allows redistribution (Apache-2.0, public domain) |

## Known plugins

| Plugin | Level | License | Notes |
|---|---|---|---|
| `wan2gp-wanflow-ui` | L2 (workflow engine) + vendored canvas | Apache-2.0 | No public upstream: treated as a fork we maintain. Canvas assets vendored unchanged into `web/assets/canvas.*` with `WANFLOW-LICENSE.txt` |
| `wan2gp-status-pro` | L2 (data only) | Public domain | Studio reads the same sources; it does not depend on the plugin's UI injections |
| `models_manager` | L2 (bundled) | WanGP Community License 2.0 | Bundled plugin, not a third-party dependency; destructive file operations stay in its own UI |
| `ImageSuite-Wan2GP` | **L1** | WanGP Community License 2.0 | Deep link plus a real SendTo hand-off driven by its `sendto.json` manifest (see below). No code copying: only the documented manifest is read |
| `wan2gp-lora-manager` | **L1** | **None declared** | No LICENSE in the upstream repository → no import, no copy. Link only |
| `wan2gp-queue-editor` | **L1** | **None declared** | Same: link only. Live queue work uses `WanGPSession` |

## Capability registry

`GET /studio/api/environment` returns:

```json
{
  "core": {"version": "18.84", "runtime": "WanGP WebUI"},
  "plugins": [
    {"id": "wan2gp-wanflow-ui", "state": "enabled", "version": "0.1.0",
     "integration": "L2", "capabilities": ["workflow.catalog", "workflow.run"], "license": "Apache-2.0"}
  ]
}
```

Plugins that ship a `sendto.json` manifest additionally carry the `sendto.inbox` capability and a `sendto` object (tab, inbox key, accepted kinds, slots).

## SendTo hand-off (Studio → plugin tab)

A Studio HTTP handler never sees a Gradio session, so it cannot write another plugin's `state[inbox_key]` itself. The hand-off is therefore a two-step protocol, entirely on documented surfaces:

1. **Park** — `POST /api/media/{id}/sendto` validates the request against the target plugin's `sendto.json` (`accepts`, slot list) and parks a one-shot id in `sendto.SendToRegistry` (bounded, 120 s TTL). The answer carries `/?studio_sendto=<id>` for the WanGP UI.
2. **Deliver** — the injected `SENDTO_BRIDGE_JS` (registered through `add_custom_js`) picks the id up in the newly opened tab, fills a hidden control that Studio inserts after the generation status (`insert_after("gen_status", …)`), and clicks it. The hidden callback receives the live session `state`, appends `{"path", "slot"}` to the manifest's `inbox_key`, and the JS then selects the target tab so the plugin's own `on_tab_select` drain loads the frame.

Rules: the id is consumed exactly once and never carries more than a path + slot; the absolute path never crosses HTTP (the status endpoint answers with names only); a missing manifest, a disabled plugin or a missing bridge each produce a distinct error the UI can explain, with **Copy path** as the manual fallback.

States: `enabled`, `disabled`, `not_installed` (plus `unlicensed` reserved for the UI). The Settings view renders this table; the Workflow view and the Models panel use the same data for their dependency states.

## Degradation rules

1. No optional plugin is imported at module import time; adapters import lazily.
2. A missing plugin turns its section into a status message, never into a crash:
   - workflow routes → `503 {"state": "not_installed"}`;
   - `/api/workflow/status` still answers `200` with the reason;
   - the canvas shows the message instead of an iframe.
3. Private WanGP bindings (`_ui_local`, `_process_inline_queue`, `server_config`) live only in `workflow_compat.py` and are wrapped in guards.
4. Studio never duplicates the runtime, the queue, the allocator, the thumbnail engine or the telemetry collector.

## Compatibility

| Component | Verified against |
|---|---|
| WanGP core | 18.84 (`shared/api.py` surface used by the plugin) |
| Python | 3.11 (uv environment in this repository) |
| Gradio / FastAPI | versions shipped with WanGP 18.84 |
| `wan2gp-wanflow-ui` | 0.1.0 (local fork, license Apache-2.0) |
| Windows | verified on Windows 11, RTX 5070 Ti Laptop 12 GB, 32 GB RAM |
| Linux / Docker | not exercised in this repository; no platform-specific paths in Studio code |

After a WanGP update, re-run `python -m pytest plugins/wan2gp_studio/tests` and open `/studio/` once to check that the private adapter points still exist.

## Adding a new optional integration

1. Add the plugin id to `KNOWN_PLUGINS` in `plugin.py` (integration level, capabilities, license).
2. Use L1 unless the plugin has an explicit license and a stable contract.
3. If L2 is required, create an adapter module like `workflow_compat.py`: lazy imports, presence probe, version gate, try/except around every private call, structured `503` when unavailable.
4. Add tests with a stub loader (see `tests/test_workflow_api.py`) and a live smoke check.
