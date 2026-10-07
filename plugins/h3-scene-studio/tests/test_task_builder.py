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
