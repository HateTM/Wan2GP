# Fork reconciliation — 2026-11-04

Compared against upstream `Javier-bat/wan2gp-wanflow-ui` @ `beb7509` (0.1.0, 2026-09-23).
The local baseline `1e173b2` is a newer private snapshot (2026-10-07), not a git
descendant of upstream: `plugin.py` and `tests/test_plugin_import.py` are byte-identical
to upstream HEAD, and every other upstream delta is either already contained here or
deliberately declined. **Nothing remains to port.**

## Upstream → fork decisions

| Upstream change | Decision |
| --- | --- |
| Model-aware workflow controls (`graph_model`, `graph_runner`, `node_registry`, `plugin_ui`, `plugin`) | Already contained in the baseline snapshot. The fork additionally carries fixes upstream lacks: `steps` → `num_inference_steps` mapping, "auto" source mode honouring `image_prompt_types_allowed`, multi-prompt G/PG splitting into one submit per unit, workflow model-unload flags, list-valued node outputs (runner + preview). |
| `ffmpeg_transcode` / `ffmpeg_normalize` / `ffmpeg_export` nodes (+ `shutil.copy2` runner) | Declined: no-op file-copy nodes, removed deliberately in the snapshot review. Porting would reintroduce them and drag `test_graph_model`'s export expectation along. |
| `tests/test_graph_model.py` ffmpeg_export tweak | Declined with the nodes. |
| README screenshots (`assets/screenshots`, ~9 MB binaries) | Declined: repository metadata, not functionality. |
| `THIRD_PARTY_NOTICES.md` / `README.es.md` / `LICENSE` | Already present in the baseline snapshot. |

## Compatibility fixes in this fork (against WanGP main)

- `shared.utils.setting_names.unknown_settings_error` was renamed to `settings_error`
  in current WanGP; updated `tests/test_graph_runner_multiprompt.py` and
  `tests/test_graph_runner_settings.py` accordingly.
- Suite green against WanGP main: 98 passed (+3 subtests).

## Fork features preserved (never overwrite with upstream pulls)

- `run_cache.py` — result cache and resume checkpoints for graph runs.
- `preflight.py` — resource preflight before graph runs.
- Compare A/B node (`assets/editor.js`, `media_ops.py`).
- FFmpeg 9 compatibility: `-vsync` → `-fps_mode` (`media_ops.py`).

Version bumped to 0.2.0 to mark the reconciled fork state (upstream remains 0.1.0).
Never update this checkout with `git pull` (unrelated histories); re-run this
content-level reconciliation instead.
