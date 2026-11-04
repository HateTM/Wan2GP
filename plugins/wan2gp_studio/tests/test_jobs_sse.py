import os
import sys
import time
from types import SimpleNamespace

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT)
sys.path.insert(0, PLUGINS_ROOT)
sys.path.insert(0, REPO_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from wan2gp_studio.plugin import WanGPStudioPlugin, _dedupe_messages  # noqa: E402


class FakeJob:
    def __init__(self):
        self._result = SimpleNamespace(success=True, cancelled=False, errors=[], generated_files=["/tmp/out.png"])

    def result(self, timeout=None):
        return self._result

    def cancel(self):
        pass


class StubSession:
    def get_model_def(self, model_type):
        return {"model_type": model_type}

    def submit_task(self, settings, callbacks=None):
        return FakeJob()


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_PLUGINS_ROOT", str(tmp_path / "empty-plugins"))
    plugin = WanGPStudioPlugin()
    plugin.server_config = {
        "image_save_path": str(tmp_path / "images"),
        "save_path": str(tmp_path / "videos"),
        "audio_save_path": str(tmp_path / "audio"),
    }
    plugin._get_session = lambda: StubSession()
    return TestClient(plugin.create_web_app())


def test_dedupe_messages_keeps_order():
    assert _dedupe_messages(["a", "a", "b", "a"]) == ["a", "b"]
    assert _dedupe_messages([]) == []


def test_job_sse_supports_cursor(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.post("/api/jobs", json={"settings": {"model_type": "demo", "prompt": "x"}})
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]

    deadline = time.time() + 10
    status = None
    while time.time() < deadline:
        status = client.get(f"/api/jobs/{job_id}").json()["status"]
        if status in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.05)
    assert status == "completed"

    full = client.get(f"/api/jobs/{job_id}/events?cursor=0")
    assert full.status_code == 200
    assert "event: end" in full.text
    assert full.text.count("id: ") >= 2

    tail = client.get(f"/api/jobs/{job_id}/events?cursor=999999")
    assert tail.status_code == 200
    assert "id: " not in tail.text
    assert "event: end" in tail.text

    header = client.get(f"/api/jobs/{job_id}/events", headers={"Last-Event-ID": "999999"})
    assert "id: " not in header.text
    assert "event: end" in header.text
