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
