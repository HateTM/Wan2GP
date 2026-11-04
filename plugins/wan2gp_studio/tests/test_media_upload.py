import io
import os
import sys
import wave

import pytest
from PIL import Image

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT)
sys.path.insert(0, PLUGINS_ROOT)
sys.path.insert(0, REPO_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

import wan2gp_studio.plugin as studio_plugin  # noqa: E402
from wan2gp_studio.plugin import WanGPStudioPlugin  # noqa: E402


def _png_bytes(size=(32, 24)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (12, 200, 120)).save(buffer, format="PNG")
    return buffer.getvalue()


def _wav_bytes(seconds=0.1, rate=8000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * int(rate * seconds))
    return buffer.getvalue()


@pytest.fixture()
def studio(tmp_path):
    plugin = WanGPStudioPlugin()
    plugin.server_config = {
        "image_save_path": str(tmp_path / "images"),
        "save_path": str(tmp_path / "videos"),
        "audio_save_path": str(tmp_path / "audio"),
    }
    return TestClient(plugin.create_web_app()), tmp_path


def test_upload_image_returns_indexed_item(studio):
    client, tmp_path = studio
    data = _png_bytes()
    response = client.post("/api/media/upload", files={"file": ("shot.png", data, "image/png")})
    assert response.status_code == 200, response.text
    item = response.json()["item"]
    assert item["kind"] == "image"
    assert item["name"] == "shot.png"
    stored = tmp_path / "images" / "shot.png"
    assert stored.is_file()
    assert stored.read_bytes() == data


def test_upload_routes_audio_to_audio_root(studio):
    client, tmp_path = studio
    response = client.post("/api/media/upload", files={"file": ("voice.wav", _wav_bytes(), "audio/wav")})
    assert response.status_code == 200, response.text
    assert response.json()["item"]["kind"] == "audio"
    assert (tmp_path / "audio" / "voice.wav").is_file()


def test_upload_rejects_unsupported_extension(studio):
    client, _ = studio
    response = client.post("/api/media/upload", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 400
    assert "Unsupported media type" in response.json()["detail"]


def test_upload_enforces_size_limit(studio, monkeypatch):
    client, _ = studio
    monkeypatch.setattr(studio_plugin, "MEDIA_UPLOAD_MAX_BYTES", 10)
    response = client.post("/api/media/upload", files={"file": ("big.png", b"x" * 4096, "image/png")})
    assert response.status_code == 413


def test_upload_resolves_name_collisions(studio):
    client, tmp_path = studio
    data = _png_bytes()
    first = client.post("/api/media/upload", files={"file": ("same.png", data, "image/png")}).json()["item"]
    second = client.post("/api/media/upload", files={"file": ("same.png", data, "image/png")}).json()["item"]
    assert first["name"] != second["name"]
    names = {path.name for path in (tmp_path / "images").iterdir()}
    assert first["name"] in names and second["name"] in names


def test_upload_sanitizes_traversal_names(studio):
    client, tmp_path = studio
    response = client.post("/api/media/upload", files={"file": ("../../evil.png", _png_bytes(), "image/png")})
    assert response.status_code == 200, response.text
    assert not (tmp_path / "evil.png").exists()
    assert not (tmp_path.parent / "evil.png").exists()
    assert (tmp_path / "images" / "evil.png").is_file()


def test_file_endpoint_streams_uploaded_bytes(studio):
    client, _ = studio
    data = _png_bytes()
    item = client.post("/api/media/upload", files={"file": ("stream.png", data, "image/png")}).json()["item"]
    response = client.get(f"/api/media/{item['id']}/file")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content == data
    missing = client.get("/api/media/not-a-real-id/file")
    assert missing.status_code == 404
