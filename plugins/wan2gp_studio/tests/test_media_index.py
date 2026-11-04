import json
import os
import sys
import time
import wave
import zipfile

import pytest
from PIL import Image

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT)
sys.path.insert(0, PLUGINS_ROOT)
sys.path.insert(0, REPO_ROOT)

from wan2gp_studio.media_index import MediaIndex, media_id_for, media_kind, parse_filename  # noqa: E402


def _make_png(path, size=(64, 48)):
    Image.new("RGB", size, (200, 40, 40)).save(path)


def _make_wav(path, seconds=0.2, rate=8000):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * int(rate * seconds))


def _make_world(path, frames=24, fps=24):
    manifest = {
        "format": "wgpworld",
        "version": 1,
        "model_type": "evoke_test",
        "width": 512,
        "height": 288,
        "fps": fps,
        "world_id": "test-world",
        "segments": [
            {"video_frames": frames, "instruction": "start", "visual_description_long": "a quiet room"},
        ],
        "world": {
            "segments": [{"video_frames": frames, "instruction": "start", "visual_description_long": "a quiet room"}],
            "perspective_view": "first person",
        },
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("tensors.safetensors", b"dummy")
        archive.writestr("thumbnail.jpg", b"\xff\xd8\xff\xd9")
        archive.writestr("poster.jpg", b"\xff\xd8\xff\xd9")


@pytest.fixture()
def media_root(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    _make_png(root / "2026-11-04-04h18m54s_seed12345_a red cube.png")
    _make_png(root / "plain.png", size=(8, 8))
    _make_wav(root / "voice.wav")
    (root / "clip.mp4").write_bytes(b"not a real mp4")
    _make_world(root / "scene.wgpworld")
    (root / "notes.txt").write_text("ignored")
    hidden = root / ".hidden"
    hidden.mkdir()
    _make_png(hidden / "secret.png")
    tmp_cache = root / "_tmp"
    tmp_cache.mkdir()
    _make_wav(tmp_cache / "scratch.wav")
    return root


@pytest.fixture()
def index(media_root, tmp_path):
    missing = tmp_path / "does-not-exist"
    instance = MediaIndex(lambda: [str(media_root), str(missing)], min_refresh_interval=0.0)
    instance.refresh(force=True)
    return instance


def test_media_kind_by_extension():
    assert media_kind("a.png") == "image"
    assert media_kind("a.MP4") == "video"
    assert media_kind("a.wav") == "audio"
    assert media_kind("a.wgpworld") == "world"
    assert media_kind("a.glb") == "3d"
    assert media_kind("a.wgpapp") == "app"
    assert media_kind("a.txt") is None


def test_parse_filename_extracts_seed_and_prompt():
    parsed = parse_filename("2026-11-04-04h18m54s_seed12345_a red cube.png")
    assert parsed["seed"] == 12345
    assert parsed["prompt_hint"] == "a red cube"
    assert parse_filename("plain.png") == {"seed": None, "prompt_hint": "plain"}


def test_media_id_is_stable_and_path_bound():
    first = media_id_for("C:/data/a.png")
    assert first == media_id_for("C:/data/a.png")
    assert first != media_id_for("C:/data/b.png")
    assert len(first) == 16


def test_scan_classifies_and_skips_service_dirs(index, media_root):
    assert index.roots() == [str(media_root.resolve())]
    stats = index.stats()
    assert stats["total"] == 5
    assert stats["kinds"] == {"image": 2, "audio": 1, "video": 1, "world": 1}


def test_query_filters_sort_and_pagination(index):
    images = index.query(kind="image")
    assert images["total"] == 2
    worlds = index.query(kind="world")
    assert [item["name"] for item in worlds["items"]] == ["scene.wgpworld"]

    by_name = index.query(sort="name_asc")
    names = [item["name"] for item in by_name["items"]]
    assert names == sorted(names, key=str.casefold)

    page = index.query(limit=2, offset=1, sort="name_asc")
    assert page["total"] == 5
    assert len(page["items"]) == 2
    assert page["offset"] == 1


def test_query_search_matches_prompt_hint(index):
    found = index.query(q="red cube")
    assert [item["name"] for item in found["items"]] == ["2026-11-04-04h18m54s_seed12345_a red cube.png"]
    assert found["items"][0]["seed"] == 12345


def test_facts_are_cheap_and_survive_broken_files(index):
    image = index.query(q="plain.png")["items"][0]
    assert (image["width"], image["height"]) == (8, 8)

    world = index.query(kind="world")["items"][0]
    assert world["model_type"] == "evoke_test"
    assert world["resolution"] == "512x288"
    assert world["duration"] == 1.0
    assert world["segment_count"] == 1

    video = index.query(kind="video")["items"][0]
    assert video["kind"] == "video"  # mutagen failed, no exception


def test_detail_reads_core_parsers_without_crashing(index):
    world = index.query(kind="world")["items"][0]
    detail = index.detail(index.get(world["id"]))
    assert detail["world"]["frame_count"] == 24
    assert detail["world"]["segment_count"] == 1
    assert detail["world"]["segments"][0]["description"] == "a quiet room"

    video = index.query(kind="video")["items"][0]
    video_detail = index.detail(index.get(video["id"]))
    assert video_detail["metadata"] is None  # unreadable container, no exception


def test_refresh_picks_up_new_files(index, media_root):
    before = index.stats()["total"]
    _make_png(media_root / "added.png")
    index.refresh(force=True)
    assert index.stats()["total"] == before + 1


# -- incremental scanning -------------------------------------------------


def test_full_scan_reports_visited_directories(index):
    scan = index.stats()["scan"]
    assert scan["mode"] == "full"
    assert scan["visited_directories"] >= 1
    assert scan["reused_directories"] == 0
    assert scan["files"] == index.stats()["total"]


def test_incremental_scan_reuses_unchanged_directories(index):
    index.refresh(force=True)  # seed the directory cache
    index.refresh(wait=True)  # nothing changed: pure reuse
    scan = index.stats()["scan"]
    assert scan["mode"] == "incremental"
    assert scan["visited_directories"] == 0
    assert scan["reused_directories"] == scan["directories"]
    assert index.stats()["total"] == 5


def test_incremental_scan_detects_new_file(index, media_root):
    index.refresh(force=True)
    time.sleep(0.05)  # directory mtime resolution is coarse on some filesystems
    _make_png(media_root / "added.png")
    index.refresh(wait=True)
    scan = index.stats()["scan"]
    assert scan["mode"] == "incremental"
    assert scan["visited_directories"] >= 1
    assert index.stats()["total"] == 6


def test_incremental_scan_detects_new_subdirectory(index, media_root):
    index.refresh(force=True)
    time.sleep(0.05)
    nested = media_root / "sub"
    nested.mkdir()
    _make_png(nested / "deep.png")
    index.refresh(wait=True)
    assert index.stats()["total"] == 6
    assert index.query(q="deep.png")["items"][0]["relative"].replace("\\", "/") == "sub/deep.png"


def test_incremental_scan_drops_deleted_files(index, media_root):
    index.refresh(force=True)
    time.sleep(0.05)
    (media_root / "plain.png").unlink()
    index.refresh(wait=True)
    assert index.stats()["total"] == 4
    assert index.query(q="plain.png")["total"] == 0


def test_index_file_survives_incremental_scan(index, media_root):
    index.refresh(force=True)
    path = media_root / "single.png"
    _make_png(path)
    assert index.index_file(str(path)) is not None
    index.refresh(wait=True)  # incremental: single.png lives in a cached directory
    assert index.query(q="single.png")["total"] == 1


def test_full_scan_reconciles_overwritten_files(index, media_root):
    """Overwriting in place does not touch the parent directory, so an
    incremental pass keeps the old facts until the next full reconcile."""
    index.refresh(force=True)
    before = index.query(q="plain.png")["items"][0]
    assert before["size"] > 0
    time.sleep(0.05)
    _make_png(media_root / "plain.png", size=(96, 72))
    incremental = index.query(q="plain.png")["items"][0]
    assert incremental["size"] == before["size"]  # stale by design
    index.refresh(force=True)
    refreshed = index.query(q="plain.png")["items"][0]
    assert refreshed["size"] != before["size"]
    assert (refreshed["width"], refreshed["height"]) == (96, 72)


def test_index_file_updates_directory_cache_for_upload(index, media_root):
    index.refresh(force=True)
    path = media_root / "upload.png"
    _make_png(path)
    entry = index.index_file(str(path))
    with index._lock:
        cached = index._dir_cache[os.path.normcase(os.path.abspath(str(media_root)))]
        assert any(item["id"] == entry["id"] for item in cached["entries"])


def test_delete_requires_known_id_and_respects_roots(index, media_root):
    assert index.delete("missing-id") is False
    item = index.query(q="plain.png")["items"][0]
    assert index._inside_roots(item["path"]) is True
    assert index._inside_roots(os.path.join(os.path.dirname(str(media_root)), "other.png")) is False
    assert index.delete(item["id"]) is True
    assert not os.path.exists(item["path"])
    assert index.stats()["total"] == 4


def test_index_file_adds_one_entry_without_rescan(index, media_root):
    before = index.stats()["total"]
    path = media_root / "single.png"
    _make_png(path)
    entry = index.index_file(str(path))
    assert entry and entry["kind"] == "image"
    assert index.stats()["total"] == before + 1
    assert index.index_file(str(media_root / "notes.txt")) is None
    assert index.index_file(str(media_root / "missing.png")) is None


def test_symlink_escape_is_rejected(index, media_root, tmp_path):
    outside = tmp_path / "outside.png"
    _make_png(outside)
    link = media_root / "escape.png"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available on this platform")
    assert index._inside_roots(str(link)) is False
    assert index.index_file(str(link)) is None
    assert index.delete(media_id_for(str(link))) is False


def test_scan_keeps_entries_indexed_during_the_walk(index, media_root):
    """A background scan that started before index_file() must not drop it."""
    live = {
        "id": "live-entry", "path": str(media_root / "later.png"), "name": "later.png",
        "relative": "later.png", "root": str(media_root), "kind": "image",
        "size": 1, "mtime": 0.0, "mtime_ns": time.time_ns() + 10**9,
    }
    with index._lock:
        index._entries["live-entry"] = live
    index._do_scan()  # walk cannot see later.png (it is not on disk)
    assert index.get("live-entry") is not None


def test_thumbnail_bytes_use_shared_engine(index):
    pytest.importorskip("shared.deepy.thumbnails")
    from wan2gp_studio.media_index import thumbnail_bytes

    image = index.query(q="plain.png")["items"][0]
    data = thumbnail_bytes(image["path"])
    assert data and data[:2] == b"\xff\xd8"
