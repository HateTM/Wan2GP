# WanGP Studio — User Guide

WanGP Studio is the lightweight web workspace bundled with this fork as the `plugins/wan2gp_studio` plugin. It drives the **already running** WanGP runtime: one process, one model loader, one native queue. Studio never starts a second runtime and never loads models by itself.

## Requirements

- WanGP **18.84 or newer** (the plugin declares `wan2gp_version: 18.84`).
- A working WanGP installation with at least one model available locally.
- Optional plugins (see `INTEGRATION.md`) — Studio works without them and shows their state instead.

## Install and upgrade

1. The plugin lives in `plugins/wan2gp_studio`. Enable it in the WanGP **Plugin Manager** (or add `wan2gp_studio` to `enabled_plugins` in `wgp_config.json`).
2. Restart WanGP. Startup log should contain `Loaded App: WanGP Studio (from wan2gp_studio)`.
3. Open `http://<host>:<port>/studio/`.

Upgrade: pull the branch, restart WanGP, reload the page. Studio keeps no database; the only state is `workflow` JSON files inside the plugin folder.

Uninstall: disable the plugin in the Plugin Manager and restart. Generated media and workflows stay on disk.

## Views

| View | Purpose |
|---|---|
| **Dashboard** | Runtime, library and activity overview; quick jumps to other views |
| **Workflow** | Model library + real node canvas (WanFlow UI) + inspector; quick generation and saved workflows |
| **Gallery** | Media Center: images, videos, audio, Worlds; search, filters, sort, lightbox, upload, delete |
| **Resources** | Read-only GPU / RAM / CPU / process telemetry and Studio activity |
| **Settings** | Read-only diagnostics: plugin states, integration levels, licenses, media roots |

Deep links: `#dashboard`, `#workflow`, `#gallery`, `#resources`, `#settings`.

## Generate

1. Pick a model in the **Models** panel (green dot = model files available locally; grey = missing, downloading happens on first run).
2. Edit the prompt and the full settings JSON in the **Inspector**; load a native preset if the model ships one.
3. Press **Run generation**. The task goes to the native WanGP queue; progress arrives over SSE; **Cancel** stops it.
4. Results appear in the native output folders and in **Gallery** after a rescan.

## Gallery

- Filters: All / Images / Videos / Audio / Worlds / 3D; search matches file names and prompt hints; six sort modes.
- Cards are virtualized: only the visible window is rendered, thumbnails are produced on demand by WanGP's own thumbnail engine.
- Lightbox: preview, facts (type, size, dimensions, duration, seed, model, date), prompt with **Copy**, **Use settings** (loads the generation parameters back into the inspector), **Send to plugin** (real SendTo, see below), **Copy path**, **Download**, **Delete**.
- **Select** mode enables multi-select and bulk delete. Deletion is permanent and also removes the `.json` sidecar when present.
- **Upload** (button or drag & drop) copies images/videos/audio into the matching WanGP output root, sanitizes names and never overwrites existing files.
- Worlds (`.wgpworld`) are shown with their poster and manifest facts; exploration stays in the native Worlds gallery.

## Send to plugin (SendTo)

If an installed plugin ships a `sendto.json` manifest (Image Suite does: *Img2Img*, *MultiCanvas*, *Modify*), the lightbox shows a **Send to plugin** row. Pick a slot, press **Send**, and Studio opens the WanGP UI with a one-shot hand-off: the frame lands in that plugin's inbox and its tab is selected, so the image is already loaded in the chosen slot — no clipboard pasting.

- The hand-off is one-shot and expires after two minutes; send again if the tab sat idle.
- Popups must be allowed for the WanGP origin; if the browser blocks the tab, Studio shows the URL to open.
- Without a SendTo-capable plugin the row shows "No SendTo target" and **Copy path** stays as the manual fallback.

## Workflow

- The canvas is the WanFlow UI editor served through Studio (`web/assets/canvas.*`, Apache-2.0, see attribution).
- **Save** stores the graph as `wan2gp-wanflow-ui` JSON in the plugin's `workflows/` folder; the selector at the top lists saved and shipped examples.
- **Run** submits the graph to the native queue through Studio's facade; node states update over SSE; **Cancel** requests cancellation at the next node check.
- Reusable blocks: select a group and press *Save as reusable block* in the inspector; saved blocks appear in the canvas palette and can be inserted into other graphs. Deleting a block asks for a second click in the palette.
- Execution requires the optional `wan2gp-wanflow-ui` plugin. Without it the view shows `not_installed` and everything else keeps working.
- Import/export: `GET /studio/api/workflow/workflows/{id}/export` and `POST /studio/api/workflow/import`. Legacy `wan2gp-workflows-v2` (`stages`) files are migrated automatically with a warning. ComfyUI **API** graphs and ComfyUI **UI-format** graphs are imported as opaque `comfyui_node` nodes — layout, values and links preserved — and exported back in the same ComfyUI format. Neither is executable inside WanGP.

## Resources

Values come from the sources WanGP already owns: NVML for GPU facts (utilization, VRAM, temperature, power, fan), psutil for RAM/CPU/process, Studio's own registries for jobs and workflow runs. When a value is unavailable it is shown as `unavailable`, never as zero. The view polls only while it is visible.

## Settings

Read-only diagnostics: the capability registry (plugin states, integration level L1/L2, license), core version and the media roots being indexed. Studio never changes WanGP settings — use the native UI for that.

## Keyboard

- `/` focuses the active search field.
- `Esc` closes the lightbox.
- `Enter` / `Space` on a media card opens the lightbox or toggles selection in Select mode.
