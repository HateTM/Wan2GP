import json
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


def test_job_repeat_resubmits_the_same_settings(tmp_path, monkeypatch):
    """Generation History: a finished job can be re-submitted with its
    original settings through POST /api/jobs/{id}/repeat."""
    monkeypatch.setenv("STUDIO_PLUGINS_ROOT", str(tmp_path / "empty-plugins"))
    plugin = WanGPStudioPlugin()
    plugin.server_config = {
        "image_save_path": str(tmp_path / "images"),
        "save_path": str(tmp_path / "videos"),
        "audio_save_path": str(tmp_path / "audio"),
    }
    session = StubSession()
    session.submitted = []
    original_submit = session.submit_task

    def tracking_submit(settings, callbacks=None):
        session.submitted.append(json.loads(json.dumps(settings)))
        return original_submit(settings, callbacks=callbacks)

    session.submit_task = tracking_submit
    plugin._get_session = lambda: session
    client = TestClient(plugin.create_web_app())

    settings = {"model_type": "t2v-test", "prompt": "same prompt", "steps": 4}
    first = client.post("/api/jobs", json={"settings": settings})
    assert first.status_code == 200, first.text
    job_id = first.json()["job_id"]

    repeat = client.post(f"/api/jobs/{job_id}/repeat")
    assert repeat.status_code == 200, repeat.text
    repeat_id = repeat.json()["job_id"]
    assert repeat_id != job_id

    deadline = time.time() + 10
    while time.time() < deadline and len(session.submitted) < 2:
        time.sleep(0.1)
    assert session.submitted == [settings, settings]

    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["settings"]["prompt"] == "same prompt"


def test_job_repeat_unknown_job_returns_404(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_PLUGINS_ROOT", str(tmp_path / "empty-plugins"))
    plugin = WanGPStudioPlugin()
    plugin.server_config = {}
    plugin._get_session = lambda: StubSession()
    client = TestClient(plugin.create_web_app())
    assert client.post("/api/jobs/does-not-exist/repeat").status_code == 404


def test_finished_jobs_persist_and_repeat_after_restart(tmp_path, monkeypatch):
    """V4.4: terminal jobs survive a host restart via the on-disk history,
    and a restart-era repeat resubmits the stored settings."""
    from fastapi.testclient import TestClient as _TC
    from wan2gp_studio.plugin import WanGPStudioPlugin as _Plugin

    workspaces = tmp_path / "workspaces"

    def build():
        monkeypatch.setenv("STUDIO_PLUGINS_ROOT", str(tmp_path / "empty-plugins"))
        plugin = _Plugin()
        plugin.server_config = {
            "image_save_path": str(tmp_path / "images"),
            "save_path": str(tmp_path / "videos"),
            "audio_save_path": str(tmp_path / "audio"),
            "workspaces_dir": str(workspaces),
        }
        session = StubSession()
        plugin._get_session = lambda: session
        return _TC(plugin.create_web_app()), session

    client, _ = build()
    settings = {"model_type": "t2v-test", "prompt": "persist me"}
    first = client.post("/api/jobs", json={"settings": settings})
    assert first.status_code == 200, first.text
    job_id = first.json()["job_id"]
    deadline = time.time() + 10
    while time.time() < deadline:
        if client.get(f"/api/jobs/{job_id}").json().get("status") == "completed":
            break
        time.sleep(0.1)
    history_path = workspaces / "studio_jobs.json"
    assert history_path.is_file()
    assert any(item["id"] == job_id for item in json.loads(history_path.read_text(encoding="utf-8")))

    # "restart": a brand-new plugin instance over the same workspaces dir
    client2, session2 = build()
    listing = client2.get("/api/jobs").json()
    assert any(job["id"] == job_id for job in listing), listing
    repeat = client2.post(f"/api/jobs/{job_id}/repeat")
    assert repeat.status_code == 200, repeat.text
    deadline = time.time() + 10
    while time.time() < deadline and len(getattr(session2, "submitted", [])) < 1:
        time.sleep(0.1)
