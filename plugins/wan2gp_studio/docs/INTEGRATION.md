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
| `ImageSuite-Wan2GP` | **L1** | WanGP Community License 2.0 | Deep link only; no code copying. Studio opens the native UI and copies the selected file path |
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
