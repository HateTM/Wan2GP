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
