# H3 Scene Studio v2.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a scene library (full-settings snapshots), story chains (N scenes → N queue tasks via `submit_manifest`), and a benchmark-measured generation recipe (832x480 / 6 steps) to the h3-scene-studio plugin.

**Architecture:** Pure logic (persistence, H3 frame grid, task building) goes into a new dependency-free module `scene_store.py` with pytest coverage. UI wiring (two new accordions + recipe on push) goes into `plugin.py`, which already owns the tab, `collect()` snapshot logic, and the `api_session` channel. `engine.py` and `vocab.py` are untouched.

**Tech Stack:** Python 3, Gradio (via WanGP plugin API `WAN2GPPlugin`), pytest, JSON file storage.

**Spec:** `docs/superpowers/specs/2026-10-07-h3-scene-studio-v2.1-design.md`

## Global Constraints

- Python: use `env_uv/Scripts/python.exe`; run tests with `env_uv/Scripts/python.exe -m pytest plugins/h3-scene-studio/tests -v`.
- No new pip dependencies; stdlib + gradio + `shared.utils.plugins` only.
- `engine.py` and `vocab.py` must not be modified.
- Existing behavior of photo sets (`PHOTOS_DIR`) and both existing buttons must not change.
- Recipe constants (from benchmark `benchmarks/run-addendum`): `RECIPE_RESOLUTION = "832x480"`, `RECIPE_STEPS = 6`.
- Scene/chain JSON is UTF-8, `ensure_ascii=False` (Cyrillic names are first-class).
- The working tree contains user-local artifacts; commit ONLY files under `plugins/h3-scene-studio/` and `docs/superpowers/`.
- Chain model choices (hardcoded in plugin, from `finetunes/`): `minimax_h3_10eros_max_b5_ref2va` (default), `minimax_h3_ref2va_pruned`, `minimax_h3_ref2va`.

## Review Focus

1. **Resolution dropdown vs non-H3 models**: if `832x480` is not among the current model's choices when pushing, the app must show a status hint, never crash or silently drop the prompt push. Test: Task 4 step 5 (manual) + defensive `gr.update` wrapper in code.
2. **Unsaved photo uploads in a chain scene**: Gradio temp file paths die between sessions; every chain scene must reference either a saved photo set (paths under `PHOTOS_DIR`) or copies persisted under `PHOTOS_DIR/_current`. Test: Task 5 step 3 asserts the copy helper.
3. **Invalid `model_type` in a manifest task**: `submit_manifest` must surface the validation error as `gr.Error` text, and the queue must not contain a half-added batch. Test: Task 6 step 3 (manual with a fake model name).
4. **Degenerate `shotSec` values** (0, absent, 20): `frames_from_seconds` must clamp to the H3 grid (`≥ 5` frames, 17k+5 form) — `0.1с → 5`, `3с → 73`, `5с → 124`, `10с → 243`. Test: Task 2 steps 1-4.
5. **Cyrillic scene names on Windows NTFS**: save/load/delete round-trip with names like `кухня-утро v2!` must work (illegal chars sanitized, legal Cyrillic kept). Test: Task 1 steps 1-4.

---

### Task 1: `scene_store.py` — scene persistence

**Files:**
- Create: `plugins/h3-scene-studio/scene_store.py`
- Test: `plugins/h3-scene-studio/tests/test_scene_store.py`
- Create: `plugins/h3-scene-studio/tests/__init__.py` (empty)

**Interfaces:**
- Consumes: nothing (stdlib only).
- Produces: `sanitize_name(name) -> str`, `scene_path(name) -> str`, `save_scene(name, settings, photo_set="", prompt="") -> (name, path)`, `load_scene(name) -> dict`, `delete_scene(name) -> None`, `list_scenes() -> list[str]`. All later tasks import these from `scene_store`.

- [ ] **Step 1: Write the failing tests**

```python
# plugins/h3-scene-studio/tests/test_scene_store.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import scene_store as ss


def test_sanitize_keeps_cyrillic_and_dashes():
    assert ss.sanitize_name("кухня-утро") == "кухня-утро"


def test_sanitize_replaces_illegal_and_falls_back():
    assert ss.sanitize_name('a<b>:"|?*') == "a_b______"
    assert ss.sanitize_name("   ").startswith("сцена-")
    assert ss.sanitize_name(None).startswith("сцена-")


def test_save_load_delete_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "SCENES_DIR", str(tmp_path))
    name, path = ss.save_scene("кухня v2!", {"mood": "shy", "shotSec": 5},
                               photo_set="мария", prompt="PROMPT")
    assert os.path.isfile(path)
    doc = ss.load_scene(name)
    assert doc["settings"]["mood"] == "shy"
    assert doc["photo_set"] == "мария"
    assert doc["prompt"] == "PROMPT"
    assert "created" in doc
    assert ss.list_scenes() == [doc["name"]]
    ss.delete_scene(name)
    assert ss.list_scenes() == []


def test_list_scenes_empty_and_sorted(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "SCENES_DIR", str(tmp_path))
    assert ss.list_scenes() == []
    ss.save_scene("b", {})
    ss.save_scene("a", {})
    assert ss.list_scenes() == ["a", "b"]


def test_load_scene_missing_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "SCENES_DIR", str(tmp_path))
    try:
        ss.load_scene("нет-такой")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `env_uv/Scripts/python.exe -m pytest plugins/h3-scene-studio/tests/test_scene_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scene_store'`

- [ ] **Step 3: Implement `scene_store.py`**

```python
"""Scene persistence for H3 Scene Studio: JSON snapshots under scenes/.

Dependency-free (no gradio, no wgp imports) so it is pytest-testable.
"""

import json
import os
import re
import time

SCENES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenes")

_ILLEGAL = re.compile(r"[^\w\u0400-\u04FF\- ]")


def sanitize_name(name):
    name = _ILLEGAL.sub("_", (name or "").strip())
    return name or f"сцена-{time.strftime('%Y%m%d-%H%M%S')}"


def scene_path(name):
    return os.path.join(SCENES_DIR, sanitize_name(name) + ".json")


def save_scene(name, settings, photo_set="", prompt=""):
    os.makedirs(SCENES_DIR, exist_ok=True)
    doc = {
        "name": sanitize_name(name),
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "settings": settings or {},
        "photo_set": photo_set or "",
        "prompt": prompt or "",
    }
    path = os.path.join(SCENES_DIR, doc["name"] + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return doc["name"], path


def load_scene(name):
    path = os.path.join(SCENES_DIR, sanitize_name(name) + ".json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def delete_scene(name):
    path = os.path.join(SCENES_DIR, sanitize_name(name) + ".json")
    if os.path.isfile(path):
        os.remove(path)


def list_scenes():
    if not os.path.isdir(SCENES_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(SCENES_DIR) if f.endswith(".json"))
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `env_uv/Scripts/python.exe -m pytest plugins/h3-scene-studio/tests/test_scene_store.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add plugins/h3-scene-studio/scene_store.py plugins/h3-scene-studio/tests/
git commit -m "h3-scene-studio: add scene_store persistence module with tests"
```

---

### Task 2: H3 frame grid + chain task builder

**Files:**
- Modify: `plugins/h3-scene-studio/scene_store.py` (append)
- Test: `plugins/h3-scene-studio/tests/test_task_builder.py` (new)

**Interfaces:**
- Consumes: `scene_store` from Task 1.
- Produces: `frames_from_seconds(sec) -> int` (H3 17k+5 grid, clamped ≥ 5); constants `RECIPE_RESOLUTION = "832x480"`, `RECIPE_STEPS = 6`; `build_task(prompt, scene, model_type, photo_paths) -> dict` where `scene` is `{"settings": {...}, "photo_set": str}` and `photo_paths` is a list of filesystem paths. This dict is submitted via `api_session.submit_manifest` in Task 6.

- [ ] **Step 1: Write the failing tests**

```python
# plugins/h3-scene-studio/tests/test_task_builder.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import scene_store as ss


def test_frames_grid_matches_real_presets():
    assert ss.frames_from_seconds(5) == 124   # user's 5s presets
    assert ss.frames_from_seconds(10) == 243  # user's 10s presets
    assert ss.frames_from_seconds(3) == 73
    assert ss.frames_from_seconds(4) == 107


def test_frames_clamps_degenerate_values():
    assert ss.frames_from_seconds(0) == 5
    assert ss.frames_from_seconds(-3) == 5
    assert ss.frames_from_seconds(0.1) == 5
    v = ss.frames_from_seconds(20)
    assert v >= 5 and v % 17 == 5


def test_build_task_shape_and_recipe():
    scene = {"settings": {"shotSec": 5, "mood": "shy"}, "photo_set": "мария"}
    t = ss.build_task("PROMPT", scene, "minimax_h3_10eros_max_b5_ref2va",
                      ["/x/ref1.jpg", "/x/ref2.jpg", "/x/ref3.jpg"])
    assert t["model_type"] == "minimax_h3_10eros_max_b5_ref2va"
    assert t["prompt"] == "PROMPT"
    assert t["resolution"] == "832x480"
    assert t["num_inference_steps"] == 6
    assert t["video_length"] == 124
    assert t["image_refs"] == ["/x/ref1.jpg", "/x/ref2.jpg", "/x/ref3.jpg"]
    assert t["seed"] == -1


def test_build_task_caps_refs_and_handles_no_sec():
    t = ss.build_task("P", {"settings": {}}, "m", [f"/x/{i}.jpg" for i in range(9)])
    assert len(t["image_refs"]) == 4
    assert t["video_length"] == 124  # default 5s when shotSec missing
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `env_uv/Scripts/python.exe -m pytest plugins/h3-scene-studio/tests/test_task_builder.py -v`
Expected: FAIL — `AttributeError: module 'scene_store' has no attribute 'frames_from_seconds'`

- [ ] **Step 3: Implement (append to `scene_store.py`)**

```python
# ---------------------------------------------------------------------------
# H3 generation task building
# ---------------------------------------------------------------------------

# Benchmark-measured fast recipe (benchmarks/run-addendum): H3 832x480, 6 steps.
RECIPE_RESOLUTION = "832x480"
RECIPE_STEPS = 6


def frames_from_seconds(sec):
    """Snap a duration to H3's 17k+5 frame grid at 24 fps (clamped >= 5)."""
    x = max(5, round(float(sec or 0) * 24))
    return x + (5 - x % 17) % 17


def build_task(prompt, scene, model_type, photo_paths):
    """Build one submit_manifest task dict from a scene snapshot."""
    sec = (scene.get("settings") or {}).get("shotSec") or 5
    return {
        "model_type": model_type,
        "prompt": prompt,
        "resolution": RECIPE_RESOLUTION,
        "num_inference_steps": RECIPE_STEPS,
        "video_length": frames_from_seconds(sec),
        "image_refs": list(photo_paths or [])[:4],
        "seed": -1,
        "batch_size": 1,
    }
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `env_uv/Scripts/python.exe -m pytest plugins/h3-scene-studio/tests/ -v`
Expected: PASS (all tests from Tasks 1-2)

- [ ] **Step 5: Commit**

```bash
git add plugins/h3-scene-studio/scene_store.py plugins/h3-scene-studio/tests/test_task_builder.py
git commit -m "h3-scene-studio: H3 frame grid + chain task builder with recipe constants"
```

---

### Task 3: Scene library UI (save / load / delete)

**Files:**
- Modify: `plugins/h3-scene-studio/plugin.py` (import block, setup_ui unchanged, new accordion in `create_tab`, new handlers)

**Interfaces:**
- Consumes: `scene_store` (Task 1); existing `S` component registry, `collect()`, `_sets_list()`, `_set_paths()`, `out_prompt`.
- Produces: accordion «💾 Сцены» with components `scene_name`, `scene_dd`; handlers `do_save_scene`, `do_load_scene`, `do_del_scene`. Task 4/5 build on `collect()` + `scene_dd` refresh pattern.

- [ ] **Step 1: Extend the import**

At `plugin.py:28`, after the engine import, add:

```python
from . import scene_store
```

- [ ] **Step 2: Add the accordion**

In `create_tab`, immediately after the «📷 Референсы» accordion closes (after `plugin.py:344`'s `attach_btn` row), insert:

```python
            with gr.Accordion("💾 Сцены", open=False, elem_classes="h3ss-acc"):
                gr.HTML("<div class='h3ss-note'>Сцена = все настройки вкладки + фото-набор. "
                        "Загрузка восстанавливает и настройки, и фото.</div>")
                with gr.Row():
                    scene_name = gr.Textbox(label="Имя сцены", scale=2)
                    scene_save_btn = gr.Button("💾 Сохранить сцену", scale=1)
                    scene_del_btn = gr.Button("🗑 Удалить сцену", scale=1)
                scene_dd = gr.Dropdown(label="Сохранённые сцены",
                                       choices=[(s, s) for s in scene_store.list_scenes()],
                                       interactive=True)
                scene_load_btn = gr.Button("📂 Загрузить сцену")
```

- [ ] **Step 3: Add handlers** (place near the other `do_*` handlers, ~`plugin.py:519`)

```python
        def do_save_scene(scene_name_text, setname_value, *vals):
            s = collect(*vals)
            name, _ = scene_store.save_scene(
                scene_name_text, s,
                photo_set=(setname_value or ""),
                prompt=global_prompt.get("text", "") or "")
            sets = scene_store.list_scenes()
            return gr.update(choices=[(x, x) for x in sets], value=name), \
                f"Сцена «{name}» сохранена."

        def do_load_scene(scene_choice):
            if not scene_choice:
                raise gr.Error("Выберите сцену в списке.")
            doc = scene_store.load_scene(scene_choice)
            s = doc.get("settings") or {}
            photo_set = doc.get("photo_set") or ""
            paths = self._set_paths(photo_set) if photo_set else []
            if photo_set and not paths:
                gr.Warning(f"Фото-набор «{photo_set}» не найден — загрузите фото вручную.")
            updates = []
            for k in keys:  # keys == list(S.keys()), defined at plugin.py:472
                if k == "files":
                    updates.append(paths)  # photos come from the linked set
                    continue
                v = s.get(k)
                updates.append(gr.update(value=v) if v is not None else gr.update())
            return updates + [paths]  # trailing: gallery
```

Outputs are `comps + [gallery]`: `files` is inside `comps` (it receives `paths` directly from the loop), so it must NOT be listed twice.

        def do_del_scene(scene_choice):
            if not scene_choice:
                raise gr.Error("Выберите сцену в списке.")
            scene_store.delete_scene(scene_choice)
            sets = scene_store.list_scenes()
            return gr.update(choices=[(x, x) for x in sets], value=None), \
                f"Сцена «{scene_choice}» удалена."
```

`global_prompt` — a one-entry dict declared next to `S = {}` (`global_prompt = {}`) and filled in `do_build` (`global_prompt["text"] = prompt`) so saving a scene can store the last built prompt.

- [ ] **Step 4: Wire events** (append to the events block, ~`plugin.py:556`)

```python
        scene_save_btn.click(do_save_scene,
                             inputs=[scene_name, setname] + comps,
                             outputs=[scene_dd, status])
        scene_load_btn.click(do_load_scene, inputs=[scene_dd],
                             outputs=comps + [gallery])
        scene_del_btn.click(do_del_scene, inputs=[scene_dd], outputs=[scene_dd, status])
```

- [ ] **Step 5: Manual smoke test**

Run: `env_uv/Scripts/python.exe wgp.py`, open the H3 Scene Studio tab.
Expected: accordion renders; save a scene with a Cyrillic name → appears in dropdown and as JSON in `plugins/h3-scene-studio/scenes/`; reload the page → «📂 Загрузить сцену» restores every dropdown/checkbox and the linked photo set; delete removes the JSON.

- [ ] **Step 6: Commit**

```bash
git add plugins/h3-scene-studio/plugin.py
git commit -m "h3-scene-studio: scene library UI (save/load/delete full scene snapshots)"
```

---

### Task 4: Quick recipe on «Вставить в генератор»

**Files:**
- Modify: `plugins/h3-scene-studio/plugin.py` (setup_ui, do_push, push wiring)

**Interfaces:**
- Consumes: `frames_from_seconds`, `RECIPE_RESOLUTION`, `RECIPE_STEPS` (Task 2); plugin API `request_component` (`shared/utils/plugins.py:353`, resolved in `run_component_insertion_and_setup` at `shared/utils/plugins.py:1625-1635` against `generator_tab_components`).
- Produces: `setup_ui` requests `resolution`, `num_inference_steps`, `video_length`; `do_push` returns updates for them + a status hint when the resolution choice is unavailable.

- [ ] **Step 1: Request the components** — in `setup_ui` (after `plugin.py:283`):

```python
        self.request_component("resolution")
        self.request_component("num_inference_steps")
        self.request_component("video_length")
```

- [ ] **Step 2: Extend `do_push`** (replace `do_push` at `plugin.py:501-504` and the `shotSec` slider read):

```python
        def do_push(current, shot_sec):
            if not current or not current.strip():
                raise gr.Error("Сначала соберите промпт.")
            frames = scene_store.frames_from_seconds(shot_sec)
            hint = ""
            updates = [current]
            # resolution is a model-filtered dropdown: if 832x480 is not among
            # the current choices (non-H3 model), skip it and tell the user.
            try:
                choices = [c for c in getattr(self.resolution, "choices", []) or []]
                if choices and "832x480" not in [str(c[0]) if isinstance(c, tuple) else str(c)
                                                 for c in choices]:
                    hint = " 832x480 нет в списке разрешений — выставьте вручную."
                else:
                    updates.append(gr.update(value="832x480"))
            except Exception:
                updates.append(gr.update())
            updates.append(gr.update(value=scene_store.RECIPE_STEPS))
            updates.append(gr.update(value=frames))
            updates.append("Рецепт применён: 832x480, 6 шагов, " + str(frames)
                           + " кадров." + hint + " Модель: MiniMax H3 Ref2VA.")
            return updates
```

- [ ] **Step 3: Rewire the button** (replace `push_btn.click(...)` at `plugin.py:551`):

```python
        push_btn.click(do_push, inputs=[out_prompt, S["shotSec"]],
                       outputs=[self.prompt, self.resolution,
                                self.num_inference_steps, self.video_length, status])
```

- [ ] **Step 4: Manual smoke test**

Run the app with a MiniMax H3 model selected: push a prompt → main form shows 832x480 / 6 steps / 124 frames (5 s default) and the status line. Then select a non-H3 model and push → prompt still lands, status shows the manual-resolution hint, no traceback in console.

- [ ] **Step 5: Commit**

```bash
git add plugins/h3-scene-studio/plugin.py
git commit -m "h3-scene-studio: apply benchmark recipe (832x480/6 steps) on push"
```

---

### Task 5: Chain UI (build the list in-memory)

**Files:**
- Modify: `plugins/h3-scene-studio/plugin.py` (new accordion + handlers)

**Interfaces:**
- Consumes: `collect()`, `_set_paths()`, the `do_attach`-style copy helper (to persist unsaved uploads under `PHOTOS_DIR/_current` — Review Focus 2).
- Produces: `chain_state` (`gr.State`, list of `{"settings": dict, "photo_set": str, "photos": [paths], "sec": float}`), `chain_df` (`gr.DataFrame`), `chain_model_dd`; Task 6 consumes `chain_state` + `chain_model_dd`.

- [ ] **Step 1: Add the accordion** (after the «💾 Сцены» accordion):

```python
            with gr.Accordion("📖 Цепочка (сцена = клип)", open=False, elem_classes="h3ss-acc"):
                gr.HTML("<div class='h3ss-note'>Добавьте текущие настройки как кадр. "
                        "«В очередь» = отдельная генерация на кадр, с рецептом 832x480 / 6 шагов.</div>")
                with gr.Row():
                    chain_add_btn = gr.Button("➕ Добавить текущую сцену")
                    chain_del_btn = gr.Button("✖ Убрать выбранный")
                    chain_up_btn = gr.Button("↑ Выше")
                    chain_down_btn = gr.Button("↓ Ниже")
                chain_idx = gr.Number(value=0, precision=0, label="Номер кадра")
                chain_df = gr.DataFrame(headers=["№", "Настройки", "Сек", "Фото"],
                                        interactive=False, wrap=True)
                with gr.Row():
                    chain_model_dd = gr.Dropdown(
                        label="Модель для цепочки",
                        choices=[(m, m) for m in ("minimax_h3_10eros_max_b5_ref2va",
                                                  "minimax_h3_ref2va_pruned",
                                                  "minimax_h3_ref2va")],
                        value="minimax_h3_10eros_max_b5_ref2va", interactive=True)
                    chain_submit_btn = gr.Button("▶️ Отправить цепочку в очередь",
                                                 elem_classes="h3ss-btn")
                chain_state = gr.State([])
```

- [ ] **Step 2: Add the photo-persisting helper + chain handlers**:

Wrinkle to know up front: `setname` and `files` are NOT part of the `comps` registry, so chain handlers take them as explicit inputs; `chain` is a plain python list declared next to `S = {}` (`chain = []`) — no `gr.State` mirror (the DataFrame is display-only and handlers return it fresh; if a session-restart issue appears, switch to `gr.State`).

```python
        def _persist_photos(files_list, setname_value):
            """Saved photo set wins; otherwise copy uploads under _current so
            paths survive past this session."""
            if setname_value:
                paths = self._set_paths(setname_value)
                if paths:
                    return paths
            paths = []
            if files_list:
                dst = os.path.join(PHOTOS_DIR, "_current")
                os.makedirs(dst, exist_ok=True)
                for i, f in enumerate(list(files_list)[:4], 1):
                    src = f.name if hasattr(f, "name") else str(f)
                    ext = os.path.splitext(src)[1] or ".jpg"
                    path = os.path.join(dst, f"ref{i}{ext}")
                    if os.path.abspath(src) != os.path.abspath(path):
                        shutil.copyfile(src, path)
                    paths.append(path)
            return paths

        def _df_rows(chain_list):
            return [[i + 1,
                     (sc["settings"].get("mood") or "") + "/" + (sc["settings"].get("format") or ""),
                     sc["settings"].get("shotSec"),
                     sc["photo_set"] or (f"{len(sc['photos'])} фото")]
                    for i, sc in enumerate(chain_list)]

        def chain_add(setname_value, files_list, *vals):
            s = collect(*vals)
            photos = _persist_photos(files_list, setname_value)
            chain.append({"settings": s, "photo_set": setname_value or "",
                          "photos": photos})
            return chain, gr.DataFrame(value=_df_rows(chain)), \
                f"Кадр {len(chain)} добавлен в цепочку."

        def chain_move(idx, direction):
            if not chain:
                raise gr.Error("Цепочка пуста.")
            i = int(idx or 0) - 1
            j = i + direction
            if not (0 <= i < len(chain)) or not (0 <= j < len(chain)):
                return gr.update(), gr.update()
            chain[i], chain[j] = chain[j], chain[i]
            return chain, gr.DataFrame(value=_df_rows(chain))

        def chain_remove(idx):
            if not chain:
                raise gr.Error("Цепочка пуста.")
            i = int(idx or 0) - 1
            if 0 <= i < len(chain):
                chain.pop(i)
            return chain, gr.DataFrame(value=_df_rows(chain))
```

- [ ] **Step 3: Wire events**:

```python
        chain_add_btn.click(chain_add, inputs=[setname, files] + comps,
                            outputs=[chain_state, chain_df, status])
        chain_up_btn.click(lambda idx: chain_move(idx, -1), inputs=[chain_idx],
                           outputs=[chain_state, chain_df])
        chain_down_btn.click(lambda idx: chain_move(idx, +1), inputs=[chain_idx],
                             outputs=[chain_state, chain_df])
        chain_del_btn.click(chain_remove, inputs=[chain_idx],
                            outputs=[chain_state, chain_df])
```

- [ ] **Step 4: Manual smoke test**

Add two scenes with different mood/shotSec → DataFrame shows 2 rows; ↑/↓/✖ behave; unsaved uploads end up copied under `plugins/h3-scene-studio/photos/_current/` (Review Focus 2); page reload clears the chain (accepted v2.1 simplification).

- [ ] **Step 5: Commit**

```bash
git add plugins/h3-scene-studio/plugin.py
git commit -m "h3-scene-studio: chain builder UI with persisted photo refs"
```

---

### Task 6: Submit the chain to the queue

**Files:**
- Modify: `plugins/h3-scene-studio/plugin.py` (one handler + one event line)

**Interfaces:**
- Consumes: `engine.build(scene_settings) -> (prompt, recap)` (existing, `plugin.py:498`); `scene_store.build_task(...)` (Task 2); `api_session.submit_manifest(tasks)` (`shared/api.py:829`, in-process session injected into `create_tab`).
- Produces: `chain_submit_btn` fills the live WebUI queue with one validated task per chain scene.

- [ ] **Step 1: Add the submit handler** (after Task 5's handlers):

```python
        def chain_submit(chain, model_type):
            if not chain:
                raise gr.Error("Цепочка пуста — добавьте хотя бы один кадр.")
            tasks = []
            for sc in chain:
                prompt, _recap = engine.build(dict(sc["settings"]))
                tasks.append(scene_store.build_task(prompt, sc, model_type,
                                                    sc.get("photos") or []))
            try:
                api_session.submit_manifest(tasks)
            except Exception as e:  # invalid model_type, validation, queue lock…
                raise gr.Error(f"Очередь отклонила цепочку: {e}")
            no_refs = sum(1 for t in tasks if not t["image_refs"])
            msg = f"В очередь добавлено {len(tasks)} задач. Модель: {model_type}."
            if no_refs:
                msg += f" Внимание: {no_refs} задач(а) без референсов — H3 сработает как T2VA."
            return msg
```

- [ ] **Step 2: Wire the button**:

```python
        chain_submit_btn.click(chain_submit, inputs=[chain_state, chain_model_dd],
                               outputs=[status])
```

- [ ] **Step 3: Manual smoke test**

With the app running and a photo set loaded: build a 2-scene chain, press «▶️ Отправить цепочку в очередь» → status reports 2 tasks; the main queue panel (Вкладка «Очередь») lists both with model `minimax_h3_10eros_max_b5_ref2va`, resolution 832x480, steps 6, distinct prompts. Negative test: type a bogus model name into the dropdown is impossible (fixed choices), so instead temporarily pass `model_type="нет_такой_модели"` in `chain_submit` → `gr.Error` shows the validation text and the queue stays clean (Review Focus 3). Revert.

- [ ] **Step 4: Commit**

```bash
git add plugins/h3-scene-studio/plugin.py
git commit -m "h3-scene-studio: submit chain as manifest tasks to the live queue"
```

---

### Task 7: Version bump + full pass

**Files:**
- Modify: `plugins/h3-scene-studio/plugin_info.json`
- Modify: `plugins/h3-scene-studio/_spec_check.py` — only if it asserts a plugin version/feature list (check before editing; if it doesn't reference v2.0 features, leave untouched).

- [ ] **Step 1: Bump version** — `plugin_info.json`: `"version": "2.1.0"`, description append: `"Includes scene library, story chains to the queue, and the benchmark-measured recipe (832x480 / 6 steps)."`

- [ ] **Step 2: Full test suite**

Run: `env_uv/Scripts/python.exe -m pytest plugins/h3-scene-studio/tests/ -v`
Expected: PASS (all Task 1-2 tests).

- [ ] **Step 3: Full manual pass** (one app session, H3 Ref2VA selected)

1. Save scene «тест-а», tweak two dropdowns, save scene «тест-б».
2. Load «тест-а» → dropdowns revert.
3. Load photo set, add 2 chain scenes (different shotSec), submit → 2 queue tasks with correct frames (124 vs e.g. 158) and recipe values.
4. Push single prompt → recipe hint appears, main form updated.
5. Start the queue once and confirm one generation completes normally end-to-end.

- [ ] **Step 4: Commit**

```bash
git add plugins/h3-scene-studio/plugin_info.json plugins/h3-scene-studio/_spec_check.py
git commit -m "h3-scene-studio: bump to v2.1.0 (scenes, chains, recipe)"
```

---

## Self-review notes

- Spec coverage: §3 → Tasks 1, 3; §4 → Tasks 2, 5, 6; §5 → Tasks 4, 6; §8 tests → Tasks 1-2 + Task 7 manual pass. No spec requirement left unowned.
- Type consistency: `build_task(prompt, scene, model_type, photo_paths)` signature identical in Task 2 (definition) and Task 6 (call); chain dict shape `{"settings", "photo_set", "photos"}` consistent between Tasks 5-6.
- Review Focus mapping: #1 → Task 4 step 2 code + step 4; #2 → Task 5 `_persist_photos` + step 4; #3 → Task 6 step 3; #4 → Task 2 tests; #5 → Task 1 tests.
