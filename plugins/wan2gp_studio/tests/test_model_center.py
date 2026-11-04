import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT)
sys.path.insert(0, PLUGINS_ROOT)
sys.path.insert(0, REPO_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from wan2gp_studio.plugin import WanGPStudioPlugin  # noqa: E402


class StubSession:
    def __init__(self):
        self.calls = []

    def list_model_metadata(self, **kwargs):
        self.calls.append(kwargs)
        return [
            {"model_type": "a", "name": "A", "outputs": ["image"], "family_label": "Fam", "availability": True},
            {"model_type": "b", "name": "B", "outputs": ["image"], "family_label": "Fam", "availability": {"status": "missing"}},
            {"model_type": "c", "name": "C", "outputs": ["video"], "family_label": "Other", "availability": {"status": "partial"}},
        ]


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_PLUGINS_ROOT", str(tmp_path / "empty-plugins"))
    plugin = WanGPStudioPlugin()
    plugin.server_config = {
        "image_save_path": str(tmp_path / "images"),
        "save_path": str(tmp_path / "videos"),
        "audio_save_path": str(tmp_path / "audio"),
    }
    stub = StubSession()
    plugin._get_session = lambda: stub  # instance attribute shadows the method
    return TestClient(plugin.create_web_app()), stub


def test_models_availability_parameter_is_passed_through(tmp_path, monkeypatch):
    client, stub = _client(tmp_path, monkeypatch)
    response = client.get("/api/models?availability=1&limit=5")
    assert response.status_code == 200
    assert stub.calls and stub.calls[0]["include_availability"] is True
    assert stub.calls[0]["limit"] == 5
    plain = client.get("/api/models?limit=5")
    assert plain.status_code == 200
    assert stub.calls[-1]["include_availability"] is False


def test_models_summary_aggregates_availability(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    response = client.get("/api/models/summary")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 3
    assert payload["available"] == 2  # True + partial count as available, missing does not
    assert payload["unavailable"] == 1
    assert payload["by_output"]["image"] == {"total": 2, "available": 1}
    assert payload["by_output"]["video"] == {"total": 1, "available": 1}
    assert payload["by_family"]["Fam"] == {"total": 2, "available": 1}
