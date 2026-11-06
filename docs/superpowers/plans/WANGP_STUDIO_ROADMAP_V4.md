# WanGP Studio — Roadmap v4: Production Generation Workspace

> 2026-11-06 · Draft for review. Source baseline: HateTM/Wan2GP main @ 685be03ddf1fbc5b44a67ff012eefa2acc80a60b; Studio plugin_info.json = 1.4.0.
>
> This document is an implementation plan, not an assertion that the listed behaviors already work. GPU acceptance, current-branch CI, and memory/VRAM measurements must be verified independently.
>
> Related: WANGP_STUDIO_ROADMAP_V3.md, STUDIO_INTEGRATION_ARCHITECTURE.md, WANGP_STUDIO_UI_CONCEPT.md; execution entrypoint fix: PR #1 (fix/studio-unified-workflow-run-20261106). PR #1 is a prerequisite, not yet considered released.

## 0. Product outcome and definition of success

A user opens /studio/, selects a WanGP model or a ready I2V/T2V workflow template, adds media, edits parameters in a contextual inspector, clicks the visible primary Run button, sees native queue progress and a preview, can cancel, and opens the produced asset in the Gallery. Save/reopen/repeat/reuse must preserve all meaningful model settings. The fallback direct Generate path must also work without a workflow plugin.

**Primary acceptance journey:** Media → Workflow → Generate → Result → Gallery → Repeat/Reuse.

Supported modes: T2I/I2I/T2V/I2V and other model types exactly as advertised by the installed WanGP model definitions. Never claim a mode is supported only because its UI has a tab. World, audio and 3D remain capability-driven, not artificially forced into image/video controls.

**Target workstation:** Windows 11, RTX 5070 Ti Laptop GPU 12 GB, 32 GB RAM. The Studio layer adds no second model runtime, CUDA context, MMGP allocator or generation queue. A model that cannot fit 12 GB must be shown as resource-constrained; the Studio UI must not imply universal 720p support.

## 1. Current evidence (audit 2026-11-06)

Already in main:
- Studio 1.4.0, FastAPI sub-app registered at /studio in plugins/wan2gp_studio/plugin.py; generation jobs submit through existing deepy.web_session()/WanGPSession.
- WorkflowCompat wraps the vendored wan2gp-wanflow-ui run_graph; the host canvas uses srcdoc iframe + postMessage; execution, import/export, graph save, SSE and cancellation endpoints exist.
- MediaIndex lists output roots, workspaces and workflow output folder; gallery, uploads, SendTo and generated-output sidecars exist.
- Plugin health, read-only telemetry, model catalogue/presets/LoRA inventory and Playwright gallery E2E exist.
- Current UI has a visible Run generation button for a standalone model and a separate small workflow Run button. Inspector edits selected model JSON, not selected canvas node. There is no separate Generate navigation/page.
- Only a subset of acceptance is automated: browser E2E emphasizes gallery/media; a real multi-node GPU run / cancellation / result path is not covered as a release gate.

Confirmed audit issues and implementation risks:
1. P0 — plugins/wan2gp_studio/workflow_compat.py:821-882: release_workflow_models is assigned only after successful run_graph return (line 860), so exceptional exit may skip model release. Centralize cleanup in finally, respecting the runtime/queue's resource ownership and unload flags. Test success, failure and cancellation.
2. P0 — workflow_compat.py:856: cancel_requested together with nonempty outputs can be classified completed. Define one authoritative terminal-state contract and explicitly report partial outputs.
3. P0 — plugins/wan2gp_studio/web/assets/workflow.js and studio.js: primary action differs from canvas action; workflow events bound twice and queue events duplicated. PR #1 addresses the entry point and handler duplication. Do not merge without green CI and live check.
4. P1 — current Inspector is a selected-model prompt + raw JSON editor, not a schema-driven node inspector. Model-dependent input slots and conditional controls are not surfaced.
5. P1 — gallery-to-canvas media handoff uses postMessage plus a timer rather than a positive iframe-ready acknowledgement. Prove transfer succeeds after slow initial load and frame rebuild.
6. P1 — studio.js formerly requested only 300 models, although the API supports up to 500. PR #1 raises this to 500; implement real API pagination instead of relying on a higher fixed cap.
7. P1 — results history and workflow runs are bounded in memory; durable generation/session history and recovery after a server restart are not yet a product contract.
8. P2 — diagnostic pages and visual layout still diverge from the approved WORKSPACE/LIBRARY/MANAGE/SYSTEM information architecture.

No production-readiness statement is valid from static inspection or a green CPU unit suite alone.

## 2. Immutable architecture rules

1. One native WanGP runtime and GPU queue. Use WanGPSession and the existing wanflow-ui run_graph; do not create a parallel execution engine.
2. Keep Studio in plugins/wan2gp_studio and controlled plugin adapters. No changes to wgp.py, shared/ or models/ without a separate, evidence-backed architecture decision.
3. Model definitions, capabilities, defaults, validation and LoRA come from the current runtime, not hand-written per-model lists.
4. Third-party plugins are optional. Missing/disabled/incompatible plugins produce explicit states and usable alternatives, never broken startup.
5. No second frontend backend, framework, server, GPU sampler, allocator, ffmpeg engine or thumbnail service.
6. Every major UX action must have exactly one backend command path and an idempotent/re-entrant UI state guard.
7. Respect WanFlow Apache-2.0 notices; do not vendor ImageSuite or unlicensed Tophness plugins. ImageSuite integration is deep-link/SendTo.
8. Keep data-path and filesystem operations within allowed media roots and web-auth origin protections; sanitise and validate all external paths/filenames.
9. Preserve unknown model-setting JSON keys; editor round-trips and workflow migrations must not silently erase data.
10. CPU CI does not replace Windows GPU smoke, resource profiling and long-session tests.

## 3. Releases and priority matrix

| Phase | Proposed release | Priority | Outcome | Main dependency |
| --- | --- | --- | --- | --- |
| V4.0 — execution hardening | 1.4.1 | P0 | One primary Run, correct completion/cancel/release | PR #1 + GPU smoke |
| V4.1 — model-aware Inspector | 1.5.0 | P0 | Edit selected canvas node without editing JSON | V4.0 + WanGP schema contract |
| V4.2 — media inputs/I2V/T2V | 1.6.0 | P0 | Upload/drag reference images, video, audio; validate slots | V4.1 |
| V4.3 — result continuity | 1.7.0 | P1 | Input → Run → Gallery with provenance | V4.2 |
| V4.4 — workspace persistence | 1.8.0 | P1 | Queue/history/repeat/workspace resilience | V4.3 |
| V4.5 — concept parity | 1.9.0 | P1 | UI layout and navigation per approved concept | V4.1–V4.4 |
| V4.6 — release qualification | 2.0.0 candidate | P0 gate | GPU, security, performance, docs, rollback | All above |

Versions are proposed milestone labels, not promised release dates. Avoid merging incomplete stages merely to advance the version label.

## 4. V4.0 — Generation execution hardening (P0)

Implementation tasks:
- Merge PR #1 only after its Studio unit suite, browser E2E and a manual run pass. Primary toolbar Run must execute the *live iframe graph*; the Inspector Run this model remains the simple non-graph path.
- Add a single run state machine: idle → validating → submitting → queued/running → cancelling → completed/failed/cancelled. Ignore double-clicks, repeated iframe events and stale SSE replays; do not let simultaneous submissions race before run_id arrives.
- In workflow_compat.py: normalize terminal states and partial output semantics; always execute owned cleanup on exceptions; never free a model owned by another active task. Verify interaction with native queue and MMGP.
- Guarantee safe cancellation of a running generation node and ffmpeg/postprocess nodes; cancellation_requested is not identical to cancelled. Distinguish acknowledged cancellation from forced/failed termination.
- Start a real 2-node image/video workflow with a currently installed model. Assert job visibility, per-node progress, preview/result and cancel.
- Make errors actionable: missing checkpoint, insufficient VRAM, incompatible plugin/version, invalid node params, failed file write, disconnected session.
- Render native queue health honestly: only Studio jobs or statuses the native API actually exposes.

Acceptance:
- One click → exactly one native submission; one clear terminal state.
- Correct final/partial outputs for success/failure/cancel.
- No duplicate Run, Save, Cancel, Gallery and SSE listeners after navigating repeatedly.
- No leaked model handles after failed/cancelled workflows; VRAM returns to a measured baseline after unloading, as appropriate to the selected offload policy.
- No WanGP core changes.

Primary files: workflow_compat.py, plugin.py, web/assets/workflow.js, web/assets/studio.js, tests/test_workflow_hardening.py, tests/test_jobs_sse.py, e2e/ (new generation test).

## 5. V4.1 — Contextual, model-aware Inspector (P0)

### UI contract
- Clicking a canvas node sends a typed selection event to Studio host (node_id, node_type, graph_revision). The host requests a complete model-schema/settings payload for the selected generation node.
- Inspector sections: Inputs; Model/Checkpoint/Variant; Prompt/Negative; Dimensions/FPS/Duration/Frames; Sampling/Seed/Steps/CFG; LoRA; Memory/Performance; Advanced JSON. Show only fields that the selected model advertises.
- Support model-change operation on the selected node without unexpectedly resetting prompt or unrelated valid values.
- Mark field validation errors at the control AND on the node. Explain controls hidden/disabled by capabilities, instead of silently showing irrelevant fields.
- Keep one canonical settings object per generation node; UI is a projection of it. Advanced JSON and form controls must round-trip in both directions without losing unknown keys.
- Preserve focus, editor draft and undo/redo (if supported by canvas) when other nodes are selected.
- Offer a separate Generate view for quick jobs without requiring graph assembly; share form/schema components with the node inspector, not a second renderer.

### Backend contract
- Build one normalized, versioned description of field schema from actual WanGP model definitions/default settings/capability metadata, with enum, type, bounds, conditional visibility and validation hints when they exist. If a field lacks metadata, expose it in Advanced JSON instead of inventing rules.
- Optional endpoints: GET /api/models/{type}/ui-schema and POST /api/models/{type}/validate-settings; prefer enriching an existing endpoint when compatibility allows.
- Debounce validation and model selection requests; cache keyed by model type + current runtime schema/version, with explicit refresh.

Acceptance:
- An I2V model exposes image input; T2V does not require one; image-only models never show unsupported video parameters.
- Native preset load, LoRA selection and advanced settings survive a save/reload/run cycle.
- One source of truth for selected node; no clash between the legacy model-list Inspector and canvas selection.
- Tests with representative schemas for image, video, audio and unsupported optional fields.

Primary files: web/assets/workflow.js, canvas.js (minimal vetted patch), studio.js, new inspector.js/schema adapter, plugin.py model API, tests/test_model_center.py.

## 6. V4.2 — First-class media inputs and generation modes (P0)

- Support input_image, input_video, input_audio, reference and mask nodes only when provided by WanFlow node registry. Prefer the native input-node conventions over custom Studio-specific graph edges.
- Connect Gallery → selected input node, file upload → node, drag/drop → node. Do not assume every uploaded file matches a model's media role.
- Replace the fixed timer-based media injection with handshake: iframe ready → request acknowledgement → applied node id; timeouts are visible and retryable.
- Support multiple references / keyframes / start-end frames when the installed model schema advertises them; order and slot mapping must be stable.
- Display media thumbnails, dimensions, duration, source path, compatibility and removals in Inspector; never keep decoded full-resolution media in global JS state.
- Validate actual file type and decode compatibility where feasible; never trust extension alone as an indication of safe/valid media. Respect configured upload limits.
- Use native image/video resolution choices and aspect ratio options; do not hard-code 720p as universally supported.
- Test with both 1280×720 and 720×1280 when the selected model supports them and with the user's single-item batch configuration; record VRAM, RAM, offloading and speed, not hypothetical numbers.
- Provide T2I/T2V/I2I/I2V templates based on available model capabilities. Show unsupported templates as unavailable with a reason; do not silently rewrite the graph.

Acceptance: upload/select media → render its preview → send to an input node → run a 2-node graph → generated file has expected media type; missing/invalid inputs fail before native submission. Gallery-to-canvas works after slow page loads and frame rebuilds.

Primary files: gallery.js, workflow.js, canvas.js, plugin.py media routes, workflow_compat.py and existing upload/format tests.

## 7. V4.3 — End-to-end Gallery provenance and reuse (P1)

- Persist workflow run id, source media ids, node id/title, model type, effective settings, timestamps and output paths as lightweight, versioned provenance. Merge existing WanGP metadata and sidecars rather than overwriting them.
- Gallery indexes new results immediately (event-driven index_file) and reconciles in the background. Do not block every generation on full output-tree rescans.
- Queue card opens exactly the produced asset in Gallery; lightbox can open the producing run, duplicate its workflow, reuse settings and use an output as a new input.
- Generation from direct Model/Generate path gets comparable provenance and a Repeat action with the same effective settings.
- Protect metadata integrity: atomic writes for sidecars, collision-safe names, invalidation on rename/delete, no traversal outside media roots. Avoid modifying user-owned imported sources.
- Add reliable thumbnails for image/video/World via existing Deepy. Preserve bounded DOM/browser page cache and 10k-gallery performance.

Acceptance: start with input in Gallery → complete workflow → click output → inspect exact run/model/seed → duplicate/re-run without manually reconstructing JSON. On restart, result metadata is still discoverable.

## 8. V4.4 — Project, queue and recovery model (P1)

- Distinguish native queue state, Studio-submitted standalone jobs, workflow runs and historical results. Do not claim full visibility into native tasks if the API cannot supply it.
- Offer queue drawer with status, model, current node, progress, elapsed, ETA only if reliable, errors, cancel and open result.
- Restore view after tab reload; prevent duplicate jobs after SSE reconnect. Reconcile from backend snapshots before declaring a task lost.
- Add a bounded durable event/history index (SQLite or atomic JSON for metadata only; no media bytes). Define retention, schema version, crash recovery and migration. Keep historical workflows and output references readable after restart.
- Save Workspace/project: active graph, selected model, inspector draft, view, media associations and pinned presets. Separate unsaved editor state from committed workflow graph.
- Offer deliberate Repeat/Duplicate, not automatic replay on page reconnect. Atomic workflow saves and backups before destructive migration.
- Optional integration with other plugins only via capabilities/deep-links; SendTo stays a user-initiated action.

Acceptance: navigating and reloading never submits a task; reconnect restores correct run status; saved workflow and references reopen; history does not grow without bounds.

## 9. V4.5 — Approved concept parity (P1)

Approved information architecture:
- WORKSPACE: Dashboard, Generate, Workflow.
- LIBRARY: Media Center, Image Editor.
- MANAGE: Models, Queue.
- SYSTEM: Resource Center, Settings, Plugins/Health.

Desktop layout at ~1440–1600 px: 208–224 px sidebar, 220–250 px node library, center-first canvas, 280–320 px contextual Inspector, collapsible 150–190 px execution drawer and compact 48–56 px toolbar. Smaller screens use drawers, not a permanently tiny canvas.

Interaction rules:
- Primary CTA = Run workflow on Workflow; Run generation on Generate.
- Clear selected-node highlighting; model availability, editable parameters and input compatibility appear in context.
- Status derived from API health, not hardcoded Connected labels. Missing plugin / disconnected runtime states must have explicit recovery actions.
- Keyboard actions for Save, Run, Esc/selection, undo/redo only when supported; accessible focus, keyboard node navigation and reduced-motion.
- Use existing static HTML/CSS/JS and Graph canvas. No redesign into a new SPA framework, renderer or second backend.
- Compare against WANGP_STUDIO_UI_CONCEPT.md and its SVG mockup using screenshots at 1600×900, 1440×900, 1280×800 and compact width. Keep canvas the visual priority.
- Reorganize UI modules by responsibility; avoid a giant cross-dependent studio.js. Prefer shared API/state utilities and explicit lifecycle/dispose for listeners.

Acceptance: full workflow journey is operable without legacy Gradio; quick Generate is one action from navigation; Inspector follows selected node; queue and results are visible without obscuring graph.

## 10. V4.6 — Production gate and test matrix (P0 release blocker)

### Automated tests
1. Static/contract: JS syntax, element IDs, postMessage schema/handshake, schema round-trip, graph version/migrations, unknown node preservation, plugin absence.
2. Backend unit/API: model schema, native submit mock, repeat/double submit prevention, SSE cursor replay and disconnect, pending/active/cancelled transitions, cleanup after exceptions, file-root safety, malformed inputs, oversized uploads.
3. Browser Playwright: choose model, edit Inspector, save graph, add Gallery image, run, progress, cancel, result lightbox, reload/reconnect, responsive layout and accessibility. Keep the 10k gallery stress suite.
4. Integration: vendored WanFlow ABI, native SessionJob callback mapping, supported/disabled plugins, ImageSuite SendTo, checkpoint unavailable and missing model metadata.
5. GPU Windows acceptance: real T2V and I2V with compatible installed weights, successful run and cancel during inference, repeated runs, offload/unload, GPU memory snapshots, 2–4 hour representative soak; distinguish unit tests from physical GPU checks.

### CI gates
- Existing studio-tests.yml and studio-e2e.yml remain mandatory.
- Add a dedicated Workflow E2E suite rather than relying only on gallery tests.
- The strict WANFLOW_REQUIRE_CUDA=1 path must be run on a suitable GPU runner or explicitly recorded manual workstation acceptance. Never count CPU skips as GPU pass.
- Status checks must be green on the exact head SHA; any file changed after checks requires renewed checks.
- No release cut without an auditable acceptance log and a tested rollback path.

### Performance/reliability budgets
- Measure idle process RSS/CPU, first page, inspector swap latency, 10k-gallery first screen after warm index (carry forward v3 target of <=2 seconds), SSE connection count, event history size and browser DOM nodes.
- Set numeric Studio memory overhead targets only after baseline on the target Windows laptop. No second CUDA allocation; monitor native VRAM use separately.
- Test 32 GB RAM pressure and 12 GB VRAM offload behavior with the actual selected model, not synthetic average GPU benchmarks.
- Monitor long-session memory slope, orphaned outputs, stale locks, temp uploads, stale SSE clients and high-rate progress events.

### Security/release
- Verify login-required and same-origin POST with WanGP --auth, private media routes, secure inline media Content-Type, path containment on read/delete/upload, symlink/junction and zip/world input boundaries, malicious workflow payload sizes.
- Update plugin_info, README, user guide, troubleshooting, compatibility matrix, notices and migration notes.
- Publish explicit known limitations: incompatible models, opaque nonexecutable ComfyUI nodes, optional plugins, native queue visibility, model-specific VRAM requirements.

## 11. Implementation order as reviewable PRs

| PR | Scope | Test proof | Merge condition |
| --- | --- | --- | --- |
| #1 (existing) | Primary canvas Run + duplicate handler fix + model count | Studio tests/E2E + live graph | green exact-SHA CI, GPU manual smoke |
| #2 | Workflow cleanup, terminal/cancel state, concurrent run guards | unit + native queue integration | no VRAM leak or false Completed |
| #3 | Canvas selection protocol + schema adapter + Inspector | schema round-trip, Playwright selection | input/model fields match runtime |
| #4 | Quick Generate view sharing Inspector form | API + Playwright no-graph run | real direct generation |
| #5 | Media handshakes, drop/upload/slot validation + templates | 2-node I2V/T2V E2E | no lost media on frame rebuild |
| #6 | Result provenance, exact Gallery linking, reuse | sidecar/metadata + E2E | run → result → repeat |
| #7 | Persistent history/workspaces/queue reconnect | restart/recovery + retention | no accidental resubmission |
| #8 | Visual concept parity & accessibility | screenshots + keyboard + responsive | selected node and queue UX usable |
| #9 | GPU acceptance, performance, security, docs | Windows measurement report | release candidate |

Separate small fixes may be merged independently; do not turn v4 into a single unreviewable rewrite. Update this document after every merged PR with implementation status and acceptance evidence.

## 12. Hard definition of Done

Feature DONE requires: (1) code merged, (2) backend test, (3) browser user-path test, (4) real GPU acceptance if generation/offloading is affected, (5) graceful fallback with optional plugins disabled, (6) no hidden data loss or second runtime, (7) memory/VRAM observations, and (8) docs updated. Status words "implemented" and "validated on target GPU" are different.

**Immediate next work:** Review/complete PR #1, then fix workflow model cleanup and terminal cancellation classification before expanding Inspector or rendering new controls. Shipping a beautiful canvas that cannot safely finish or cancel a generation is not v4 success.
