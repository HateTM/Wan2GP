import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import scene_store as ss


def test_is_h3_model():
    assert ss.is_h3_model("minimax_h3_10eros_max_b6_ref2va")
    assert ss.is_h3_model("minimax_h3_fl2va")
    assert not ss.is_h3_model("ltx2_25_22B_distilled_nvfp4_nsfw")
    assert not ss.is_h3_model("")
    assert not ss.is_h3_model(None)


def test_restore_value_checkboxes():
    for k in ("act_tease", "act_cum", "talk", "fixRef", "manJoin",
              "artifactFull", "pov", "act_intro"):
        assert ss.restore_value(k, "on") is True, k
        assert ss.restore_value(k, "off") is False, k


def test_restore_value_passthrough_for_non_checkboxes():
    assert ss.restore_value("mood", "shy") == "shy"
    assert ss.restore_value("shotSec", 5) == 5
    assert ss.restore_value("fAge", "asref") == "asref"
    assert ss.restore_value("mood", None) is None
