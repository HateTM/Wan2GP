import json
import os
import sys
import time
from io import BytesIO

import pytest
from PIL import Image

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT)
sys.path.insert(0, PLUGINS_ROOT)
sys.path.insert(0, REPO_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from wan2gp_studio.plugin import WanGPStudioPlugin  # noqa: E402
from wan2gp_studio.sendto import (  # noqa: E402
    SendToError,
    SendToRegistry,
    discover_manifests,
    inbox_append,
    read_manifest,
)


def _png_bytes(size=(32, 24)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (12, 200, 120)).save(buffer, format="PNG")
    return buffer.getvalue()


MANIFEST = {
    "tab": "ImageSuite",
    "inbox_key": "imagesuite_inbox",
    "payload": "frame",
    "accepts": ["image"],
    "targets": [
        {"label": "Img2Img", "slot": "img2img"},
        {"label": "MultiCanvas", "slot": "inpaint"},
        {"label": "Modify", "slot": "modify"},
    ],
}


@pytest.fixture()
def fake_plugins_root(tmp_path):
    root = tmp_path / "plugins"
    plugin = root / "ImageSuite-Wan2GP"
    plugin.mkdir(parents=True)
    (plugin / "plugin_info.json").write_text(
        json.dumps({"name": "Image Suite", "version": "0.3.0"}), encoding="utf-8"
    )
    (plugin / "sendto.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
    return root


@pytest.fixture()
def client(tmp_path, fake_plugins_root, monkeypatch):
    monkeypatch.setenv("STUDIO_PLUGINS_ROOT", str(fake_plugins_root))
    plugin = WanGPStudioPlugin()
    plugin.server_config = {
        "image_save_path": str(tmp_path / "images"),
        "save_path": str(tmp_path / "videos"),
        "audio_save_path": str(tmp_path / "audio"),
    }
    return TestClient(plugin.create_web_app()), plugin


def _upload(client, name="frame.png", data=None):
    response = client.post("/api/media/upload", files={"file": (name, data or _png_bytes(), "image/png")})
    assert response.status_code == 200, response.text
    return response.json()["item"]


# -- manifests -------------------------------------------------------------


def test_read_manifest_parses_targets(fake_plugins_root):
    manifest = read_manifest(fake_plugins_root / "ImageSuite-Wan2GP")
    assert manifest is not None
    assert manifest.plugin == "ImageSuite-Wan2GP"
    assert manifest.plugin_label == "Image Suite"
    assert manifest.inbox_key == "imagesuite_inbox"
    assert manifest.accepts == ("image",)
    assert manifest.slots() == ("img2img", "inpaint", "modify")
    assert manifest.slot_label("modify") == "Modify"
    assert manifest.slot_label("nope") is None
    assert manifest.accepts_kind("image") and not manifest.accepts_kind("video")


def test_read_manifest_requires_inbox_key(tmp_path):
    plugin = tmp_path / "Broken"
    plugin.mkdir()
    (plugin / "sendto.json").write_text(json.dumps({"tab": "Broken"}), encoding="utf-8")
    assert read_manifest(plugin) is None
    (plugin / "sendto.json").write_text("not json", encoding="utf-8")
    assert read_manifest(plugin) is None


def test_discover_manifests_ignores_plugins_without_manifest(fake_plugins_root):
    (fake_plugins_root / "Plain-Plugin").mkdir()
    manifests = discover_manifests(fake_plugins_root)
    assert set(manifests) == {"ImageSuite-Wan2GP"}


def test_inbox_append_follows_sendto_contract():
    state: dict = {}
    assert inbox_append(state, "imagesuite_inbox", "C:/a.png", "img2img") is True
    assert state["imagesuite_inbox"] == [{"path": "C:/a.png", "slot": "img2img"}]
    assert inbox_append("not-a-dict", "k", "p", None) is False  # type: ignore[arg-type]
    inbox_append(state, "other", "C:/b.png", None)
    assert state["other"] == [{"path": "C:/b.png", "slot": None}]
    for index in range(250):
        inbox_append(state, "imagesuite_inbox", f"C:/{index}.png", None)
    assert len(state["imagesuite_inbox"]) == 200


# -- registry ----------------------------------------------------------------


def _registry(fake_plugins_root, **kwargs):
    return SendToRegistry(lambda: fake_plugins_root, **kwargs)


def test_create_rejects_unknown_plugin_slot_and_kind(fake_plugins_root, tmp_path):
    registry = _registry(fake_plugins_root)
    frame = tmp_path / "frame.png"
    frame.write_bytes(_png_bytes())
    with pytest.raises(SendToError) as missing:
        registry.create(str(frame), "image", "NoSuch-Plugin", "img2img")
    assert missing.value.status_code == 409
    with pytest.raises(SendToError) as bad_slot:
        registry.create(str(frame), "image", "ImageSuite-Wan2GP", "nope")
    assert bad_slot.value.status_code == 400
    assert bad_slot.value.extra["slots"] == ["img2img", "inpaint", "modify"]
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"not a real mp4")
    with pytest.raises(SendToError) as bad_kind:
        registry.create(str(clip), "video", "ImageSuite-Wan2GP", "img2img")
    assert bad_kind.value.status_code == 400
    with pytest.raises(SendToError) as gone:
        registry.create(str(tmp_path / "deleted.png"), "image", "ImageSuite-Wan2GP", "img2img")
    assert gone.value.status_code == 404


def test_handoff_is_one_shot(fake_plugins_root, tmp_path):
    registry = _registry(fake_plugins_root)
    frame = tmp_path / "frame.png"
    frame.write_bytes(_png_bytes())
    handoff = registry.create(str(frame), "image", "ImageSuite-Wan2GP", "inpaint")
    assert registry.status(handoff.handoff_id) == "pending"
    claimed = registry.take(handoff.handoff_id)
    assert claimed is not None
    assert claimed.slot == "inpaint" and claimed.tab == "ImageSuite"
    assert claimed.path == os.path.abspath(str(frame))
    assert registry.take(handoff.handoff_id) is None
    assert registry.status(handoff.handoff_id) == "consumed"


def test_handoff_expires_after_ttl(fake_plugins_root, tmp_path):
    now = [time.time()]
    registry = _registry(fake_plugins_root, clock=lambda: now[0], ttl=30.0)
    frame = tmp_path / "frame.png"
    frame.write_bytes(_png_bytes())
    handoff = registry.create(str(frame), "image", "ImageSuite-Wan2GP", "modify")
    assert registry.status(handoff.handoff_id) == "pending"
    now[0] += 31.0  # advance the fake clock past the TTL
    assert registry.status(handoff.handoff_id) == "expired"
    assert registry.take(handoff.handoff_id) is None


def test_registry_is_bounded(fake_plugins_root, tmp_path):
    registry = _registry(fake_plugins_root, limit=2, ttl=600.0)
    frames = []
    for index in range(3):
        frame = tmp_path / f"frame{index}.png"
        frame.write_bytes(_png_bytes())
        frames.append(registry.create(str(frame), "image", "ImageSuite-Wan2GP", "img2img"))
    assert registry.peek(frames[0].handoff_id) is None  # oldest evicted
    assert registry.peek(frames[1].handoff_id) is not None
    assert registry.peek(frames[2].handoff_id) is not None


def test_targets_report_enabled_state(fake_plugins_root):
    registry = SendToRegistry(
        lambda: fake_plugins_root,
        is_enabled=lambda plugin_id: plugin_id == "ImageSuite-Wan2GP",
    )
    targets = registry.targets()
    assert [target["slot"] for target in targets] == ["img2img", "inpaint", "modify"]
    assert all(target["enabled"] for target in targets)
    other = SendToRegistry(lambda: fake_plugins_root, is_enabled=lambda plugin_id: False)
    assert all(target["enabled"] is False for target in other.targets())


def test_create_rejects_disabled_plugin(fake_plugins_root, tmp_path):
    """A disabled target must be refused at create() time, not only hidden in
    the UI: the client chooses the slot, so the API is the last gate."""
    registry = _registry(fake_plugins_root, is_enabled=lambda plugin_id: False)
    frame = tmp_path / "frame.png"
    frame.write_bytes(_png_bytes())
    with pytest.raises(SendToError) as disabled:
        registry.create(str(frame), "image", "ImageSuite-Wan2GP", "img2img")
    assert disabled.value.status_code == 409
    assert "disabled" in disabled.value.detail
    assert registry.pending() == 0


def test_bridge_refuses_handoff_for_disabled_plugin(fake_plugins_root, tmp_path):
    """Delivery-time re-check: a hand-off parked while the plugin was enabled
    must not reach an inbox after the plugin was disabled."""
    registry = _registry(fake_plugins_root)
    frame = tmp_path / "frame.png"
    frame.write_bytes(_png_bytes())
    handoff = registry.create(str(frame), "image", "ImageSuite-Wan2GP", "img2img")
    plugin = WanGPStudioPlugin()
    plugin._sendto = registry
    plugin._plugin_enabled = lambda plugin_id: False  # type: ignore[method-assign]
    state: dict = {}
    _, status = plugin._apply_sendto_handoff(state, handoff.handoff_id)
    assert status == "disabled"
    assert state == {}  # nothing was appended to any inbox
    assert registry.status(handoff.handoff_id) == "consumed"  # one-shot still holds


# -- HTTP routes ---------------------------------------------------------------


def test_targets_route_lists_manifest_slots(client):
    api, _ = client
    response = api.get("/api/sendto/targets")
    assert response.status_code == 200
    payload = response.json()
    assert payload["bridge"] is False  # no Gradio UI in tests
    assert any(target["slot"] == "img2img" for target in payload["targets"])


def test_send_media_round_trip(client):
    api, plugin = client
    item = _upload(api)
    plugin._sendto_bridge_installed = True
    response = api.post(
        f"/api/media/{item['id']}/sendto",
        json={"plugin": "ImageSuite-Wan2GP", "slot": "img2img"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["bridge"] is True
    assert payload["url"].startswith("/?studio_sendto=")
    assert payload["handoff"]["plugin"] == "ImageSuite-Wan2GP"
    assert payload["handoff"]["slot_label"] == "Img2Img"
    assert "path" not in payload["handoff"]  # the absolute path never crosses HTTP

    handoff_id = payload["handoff_id"]
    assert api.get(f"/api/sendto/{handoff_id}").json()["status"] == "pending"

    state: dict = {}
    state_after, message = plugin._apply_sendto_handoff(state, handoff_id)
    assert state_after is state
    assert message == "sent:img2img"
    inbox = state["imagesuite_inbox"]
    assert len(inbox) == 1
    assert inbox[0]["slot"] == "img2img"
    assert os.path.isfile(inbox[0]["path"])

    assert api.get(f"/api/sendto/{handoff_id}").json()["status"] == "consumed"
    again_state, again = plugin._apply_sendto_handoff({}, handoff_id)
    assert again == "expired"


def test_send_media_without_explicit_plugin_uses_single_manifest(client):
    api, _ = client
    item = _upload(api)
    response = api.post(f"/api/media/{item['id']}/sendto", json={"slot": "modify"})
    assert response.status_code == 200
    assert response.json()["handoff"]["slot"] == "modify"


def test_send_media_rejects_video_and_bad_slot(client):
    api, _ = client
    clip = _upload(api, name="clip.mp4", data=b"not a real mp4")
    wrong_kind = api.post(f"/api/media/{clip['id']}/sendto", json={"slot": "img2img"})
    assert wrong_kind.status_code == 400
    frame = _upload(api)
    wrong_slot = api.post(f"/api/media/{frame['id']}/sendto", json={"slot": "nope"})
    assert wrong_slot.status_code == 400
    assert "slots" in wrong_slot.json()["detail"]
    unknown = api.post("/api/media/does-not-exist/sendto", json={"slot": "img2img"})
    assert unknown.status_code == 404
    stranger = api.post(
        f"/api/media/{frame['id']}/sendto",
        json={"plugin": "NoSuch-Plugin", "slot": "img2img"},
    )
    assert stranger.status_code == 409


def test_environment_reports_sendto_capability(client):
    api, _ = client
    entry = {item["id"]: item for item in api.get("/api/environment").json()["plugins"]}
    suite = entry["ImageSuite-Wan2GP"]
    assert "sendto.inbox" in suite["capabilities"]
    assert suite["sendto"]["inbox_key"] == "imagesuite_inbox"
    assert suite["sendto"]["tab"] == "ImageSuite"
    assert [target["slot"] for target in suite["sendto"]["targets"]] == ["img2img", "inpaint", "modify"]


# -- wiring ----------------------------------------------------------------


def test_bridge_is_wired_into_the_gradio_ui():
    with open(os.path.join(PLUGIN_DIR, "plugin.py"), encoding="utf-8") as handle:
        source = handle.read()
    assert 'self.insert_after("gen_status", self._build_sendto_bridge)' in source
    assert "self.add_custom_js(SENDTO_BRIDGE_JS)" in source
    assert 'studio_sendto_token' in source and 'studio_sendto_trigger' in source
    assert 'studio_sendto=' in source
