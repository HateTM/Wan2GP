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


# ---------------------------------------------------------------------------
# Engine-shape <-> component-shape helpers
# ---------------------------------------------------------------------------

# Checkbox component keys: collect() stores them as "on"/"off" strings for the
# engine, but gradio Checkbox.postprocess coerces any string to bool — so a
# stored "off" would load back as True. restore_value converts on load.
CHECKBOX_KEYS = frozenset({
    "act_intro", "act_tease", "act_hj", "act_bj", "act_breast", "act_sex",
    "act_cum", "talk", "fixRef", "manJoin", "artifactFull", "pov",
})

# collect() renames these component keys for the engine; undo on load.
LOOK_RENAME = {"introLook": "introLookName", "teaseLook": "teaseLookName"}


def is_h3_model(model_type):
    """True when the active model is a MiniMax H3 family model."""
    return str(model_type or "").startswith("minimax_h3")


def restore_value(key, value):
    """Convert a stored engine-shape value back into its component value."""
    if key in CHECKBOX_KEYS:
        return value == "on"
    return value
