import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT)
sys.path.insert(0, PLUGINS_ROOT)
sys.path.insert(0, REPO_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

import wan2gp_studio.telemetry as telemetry_module  # noqa: E402
from wan2gp_studio.plugin import WanGPStudioPlugin  # noqa: E402
from wan2gp_studio.telemetry import Telemetry  # noqa: E402


def test_snapshot_shape_and_cache():
    telemetry = Telemetry(
        jobs_provider=lambda: [{
            "id": "j1", "status": "running", "model_type": "m", "phase": "denoise",
            "progress": 42, "message": "Denoising", "created_at": 1.0,
        }],
        workflow_provider=lambda: [{
            "id": "r1", "status": "running", "progress": 10, "message": "Step", "created_at": 2.0,
        }],
        cache_seconds=60,
    )
    snapshot = telemetry.snapshot()
    assert snapshot["system"]["ram_total_mb"] > 0
    assert snapshot["process"]["rss_mb"] > 0
    assert isinstance(snapshot["gpu"]["available"], bool)
    assert snapshot["studio"]["active_jobs"] == 1
    assert snapshot["studio"]["current_job"]["model_type"] == "m"
    assert snapshot["studio"]["active_workflow_runs"] == 1
    assert snapshot["sources"]["ram"] == "psutil"
    assert telemetry.snapshot() is snapshot  # cached within the window


def test_gpu_unavailable_is_reported_honestly():
    telemetry = Telemetry(lambda: [], lambda: [], cache_seconds=0)
    telemetry._nvml_ready = True
    telemetry._nvml = None
    snapshot = telemetry.snapshot()
    assert snapshot["gpu"]["available"] is False
    assert snapshot["gpu"]["source"] in ("unavailable", "nvml-error")


def test_telemetry_route_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_PLUGINS_ROOT", str(tmp_path / "empty-plugins"))
    plugin = WanGPStudioPlugin()
    plugin.server_config = {
        "image_save_path": str(tmp_path / "images"),
        "save_path": str(tmp_path / "videos"),
        "audio_save_path": str(tmp_path / "audio"),
    }
    client = TestClient(plugin.create_web_app())
    response = client.get("/api/telemetry")
    assert response.status_code == 200
    payload = response.json()
    for key in ("gpu", "system", "process", "studio", "sources"):
        assert key in payload
    assert payload["sources"]["jobs"] == "studio-session"
    assert payload["studio"]["jobs_total"] == 0
