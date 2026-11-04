import json
import os
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT)
sys.path.insert(0, PLUGINS_ROOT)
sys.path.insert(0, REPO_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from wan2gp_studio.plugin import WanGPStudioPlugin  # noqa: E402
from wan2gp_studio.workflow_compat import WorkflowCompat, WorkflowUnavailable  # noqa: E402


class StubGraphModel:
    @staticmethod
    def normalize_graph(graph):
        result = json.loads(json.dumps(graph))
        result.setdefault("nodes", [])
        result.setdefault("edges", [])
        result.setdefault("name", "Workflow")
        for index, node in enumerate(result["nodes"]):
            node.setdefault("id", f"n{index}")
            node.setdefault("enabled", True)
        return result

    @staticmethod
    def validate_graph(graph):
        if not graph.get("nodes"):
            raise ValueError("Workflow has no nodes")

    @staticmethod
    def topological_order(graph):
        return [node["id"] for node in graph["nodes"]]


class StubGraphStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def slug(value):
        return re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "workflow")).strip("-_").lower() or "workflow"

    def choices(self):
        out = []
        for path in sorted(self.root.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            out.append((str(data.get("name") or path.stem), path.stem))
        return out

    def save(self, graph, name):
        slug = self.slug(name)
        path = self.root / f"{slug}.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        return graph, path

    def load(self, slug):
        path = self.root / f"{self.slug(slug)}.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        return json.loads(path.read_text(encoding="utf-8"))

    def delete(self, slug):
        (self.root / f"{self.slug(slug)}.json").unlink(missing_ok=True)


class StubNodeRegistry:
    @staticmethod
    def build_catalog(model_defs, processes, loras, resolver):
        return {
            "nodes": [{"type": "text_prompt", "label": "Prompt", "category": "Inputs", "description": "", "ports": []}],
            "models": sorted(model_defs),
            "processes": list(processes),
            "loras": loras,
        }


class StubBlockStore:
    def __init__(self, root):
        self.root = Path(root)

    def catalog(self):
        return []


class StubGraphRunner:
    mode = "fast"
    released = []

    @staticmethod
    def run_graph(plugin, session, state, graph, inputs, *, output_root, callback=None, cancel_check=None, node_callback=None):
        for node in graph.get("nodes") or []:
            if not node.get("enabled", True):
                continue
            node_callback(node["id"], "running", None)
            if StubGraphRunner.mode == "slow":
                for _ in range(100):
                    if cancel_check and cancel_check():
                        raise InterruptedError("Cancelled")
                    time.sleep(0.05)
            else:
                callback("Step", 50)
            node_callback(node["id"], "done", {"file": str(Path(output_root) / "out.mp4")})
        return [str(Path(output_root) / "out.mp4")], {"var": "x"}

    @staticmethod
    def release_workflow_models(plugin, graph):
        StubGraphRunner.released.append(graph.get("name"))


def _stub_loader():
    graph_store_module = type("StubGraphStoreModule", (), {"GraphStore": StubGraphStore})
    block_store_module = type("StubBlockStoreModule", (), {"BlockStore": StubBlockStore})
    return {
        "graph_model": StubGraphModel,
        "graph_store": graph_store_module,
        "block_store": block_store_module,
        "node_registry": StubNodeRegistry,
        "graph_runner": StubGraphRunner,
    }


class StubHost:
    def __init__(self):
        self.session = SimpleNamespace(_ui_local=None)

    def list_model_defs(self):
        return [{"model_type": "m1", "name": "Model One"}]

    def get_default_settings(self, key):
        return {"steps": 8}

    def get_session(self):
        return self.session


def _graph():
    return {
        "name": "Test Flow",
        "nodes": [{"id": "n1", "type": "text_prompt", "params": {}, "enabled": True}],
        "edges": [],
    }


def test_unavailable_without_plugin_dir(tmp_path):
    compat = WorkflowCompat(StubHost(), plugins_root=tmp_path)
    assert compat.available() is False
    assert compat.info()["state"] == "not_installed"
    with pytest.raises(WorkflowUnavailable):
        compat.catalog()


def test_catalog_storage_and_validation_with_stub(tmp_path):
    compat = WorkflowCompat(StubHost(), plugins_root=tmp_path / "plugins", loader=_stub_loader, output_root=tmp_path / "out")
    catalog = compat.catalog()
    assert catalog["nodes"][0]["type"] == "text_prompt"
    assert catalog["models"] == ["m1"]

    assert compat.workflows() == []
    saved = compat.save(_graph(), "Test Flow")
    assert saved["id"] == "test-flow"
    assert [entry["id"] for entry in compat.workflows()] == ["test-flow"]
    assert compat.load("test-flow")["name"] == "Test Flow"

    validation = compat.validate(_graph())
    assert validation["ok"] is True and validation["order"] == ["n1"]
    broken = compat.validate({"nodes": [], "edges": []})
    assert broken["ok"] is False

    compat.delete("test-flow")
    assert compat.workflows() == []


def test_run_lifecycle_and_events(tmp_path):
    StubGraphRunner.mode = "fast"
    compat = WorkflowCompat(StubHost(), plugins_root=tmp_path / "plugins", loader=_stub_loader, output_root=tmp_path / "out")
    run = compat.start_run(_graph())
    run_id = run["run_id"]
    deadline = time.time() + 5
    while time.time() < deadline:
        snapshot = compat.snapshot(run_id)
        if snapshot["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.05)
    assert snapshot["status"] == "completed"
    assert snapshot["outputs"] == [str(tmp_path / "out" / "out.mp4")]
    assert snapshot["variables"] == {"var": "x"}
    events, latest = compat.events_after(run_id, 0)
    assert events and events[-1]["kind"] == "closed"
    again, latest2 = compat.events_after(run_id, latest)
    assert again == [] and latest2 == latest
    assert StubGraphRunner.released[-1] == "Test Flow"


def test_run_cancel(tmp_path):
    StubGraphRunner.mode = "slow"
    compat = WorkflowCompat(StubHost(), plugins_root=tmp_path / "plugins", loader=_stub_loader, output_root=tmp_path / "out")
    run_id = compat.start_run(_graph())["run_id"]
    time.sleep(0.3)
    assert compat.cancel(run_id) is True
    deadline = time.time() + 8
    while time.time() < deadline:
        snapshot = compat.snapshot(run_id)
        if snapshot["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.05)
    assert snapshot["status"] == "cancelled"
    assert compat.cancel("missing-run") is False
    StubGraphRunner.mode = "fast"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_PLUGINS_ROOT", str(tmp_path / "empty-plugins"))
    plugin = WanGPStudioPlugin()
    plugin.server_config = {
        "image_save_path": str(tmp_path / "images"),
        "save_path": str(tmp_path / "videos"),
        "audio_save_path": str(tmp_path / "audio"),
    }
    return TestClient(plugin.create_web_app())


def test_environment_lists_known_plugins(client):
    response = client.get("/api/environment")
    assert response.status_code == 200
    payload = response.json()
    assert payload["core"]["runtime"] == "WanGP WebUI"
    entries = {entry["id"]: entry for entry in payload["plugins"]}
    for known in ("wan2gp-wanflow-ui", "wan2gp-status-pro", "models_manager", "ImageSuite-Wan2GP"):
        assert known in entries
    assert entries["wan2gp-wanflow-ui"]["integration"] == "L2"
    assert entries["wan2gp-lora-manager"]["license"] == "none"


def test_workflow_routes_degrade_with_503(client):
    missing = client.get("/api/workflow/catalog")
    assert missing.status_code == 503
    assert missing.json()["detail"]["state"] == "not_installed"
    listing = client.get("/api/workflow/workflows")
    assert listing.status_code == 503
    run = client.post("/api/workflow/runs", json={"graph": _graph()})
    assert run.status_code == 503
    status = client.get("/api/workflow/status")
    assert status.status_code == 200
    assert status.json()["state"] == "not_installed"
