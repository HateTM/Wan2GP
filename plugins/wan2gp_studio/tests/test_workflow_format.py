import importlib
import json
import os
import re
import sys
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
from wan2gp_studio.workflow_compat import WorkflowCompat, WorkflowImportError  # noqa: E402

GRAPH_MODEL = importlib.import_module("wan2gp-wanflow-ui.graph_model")


class StubGraphStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def slug(value):
        return re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "workflow")).strip("-_").lower() or "workflow"

    def choices(self):
        return [(json.loads(path.read_text(encoding="utf-8")).get("name") or path.stem, path.stem)
                for path in sorted(self.root.glob("*.json"))]

    def save(self, graph, name):
        path = self.root / f"{self.slug(name)}.json"
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
        return {"nodes": [{"type": "text_prompt"}, {"type": "generate_image"}, {"type": "generate_video"}],
                "models": [], "processes": [], "loras": {}}


class StubBlockStore:
    def __init__(self, root):
        self.root = Path(root)

    def catalog(self):
        return []


class StubHost:
    def list_model_defs(self):
        return []


def _loader():
    return {
        "graph_model": GRAPH_MODEL,
        "graph_store": type("M", (), {"GraphStore": StubGraphStore}),
        "block_store": type("M", (), {"BlockStore": StubBlockStore}),
        "node_registry": StubNodeRegistry,
    }


def _compat(tmp_path):
    return WorkflowCompat(StubHost(), plugins_root=tmp_path / "plugins", loader=_loader, output_root=tmp_path / "out")


def test_round_trip_export_import(tmp_path):
    compat = _compat(tmp_path)
    graph = {"name": "Round Trip", "nodes": [{"id": "n1", "type": "text_prompt", "params": {"text": "hi"}, "enabled": True}], "edges": []}
    saved = compat.save(graph, "Round Trip")
    exported = compat.export_workflow(saved["id"])
    assert exported["schema"] == "wan2gp-wanflow-ui"
    assert exported["version"] == 1

    imported = compat.import_workflow(exported)
    assert imported["id"] == "round-trip"
    assert imported["legacy"] is False
    assert imported["unknown_nodes"] == []
    assert imported["node_count"] == 1
    assert compat.load("round-trip")["nodes"][0]["type"] == "text_prompt"


def test_legacy_v1_stage_workflow_is_migrated(tmp_path):
    compat = _compat(tmp_path)
    legacy = {
        "name": "Legacy Flow",
        "aspect_ratio": "1024x1024",
        "stages": [{
            "id": "s1",
            "stage_type": "generation",
            "settings": {"model_type": "moss_image_sft", "image_mode": 1, "num_inference_steps": 8},
            "prompt": "legacy prompt",
        }],
    }
    imported = compat.import_workflow(legacy)
    assert imported["legacy"] is True
    assert any("Imported from v1" in warning for warning in imported["warnings"])
    stored = compat.load(imported["id"])
    types = [node["type"] for node in stored["nodes"]]
    assert "generate_image" in types
    assert types[-1] == "generate_image"
    assert stored["nodes"][-1]["params"]["legacy_stage_type"] == "generation"


def test_unknown_nodes_are_preserved_and_reported(tmp_path):
    compat = _compat(tmp_path)
    graph = {"name": "Unknown", "nodes": [{"id": "u1", "type": "mystery_node", "params": {"x": 1}, "enabled": True}], "edges": []}
    imported = compat.import_workflow(graph)
    assert imported["unknown_nodes"] == ["mystery_node"]
    stored = compat.load(imported["id"])
    assert stored["nodes"][0]["type"] == "mystery_node"


def test_comfyui_payload_is_rejected_with_report(tmp_path):
    compat = _compat(tmp_path)
    with pytest.raises(WorkflowImportError) as error:
        compat.import_workflow({"nodes": [{"id": 1, "type": "KSampler"}], "links": []})
    assert error.value.report.get("format") == "comfyui"


def test_export_import_routes_against_installed_plugin(tmp_path, monkeypatch):
    plugin = WanGPStudioPlugin()
    plugin.server_config = {
        "image_save_path": str(tmp_path / "images"),
        "save_path": str(tmp_path / "videos"),
        "audio_save_path": str(tmp_path / "audio"),
    }
    client = TestClient(plugin.create_web_app())

    exported = client.get("/api/workflow/workflows/draft-video-t2v/export")
    assert exported.status_code == 200, exported.text
    payload = exported.json()
    assert payload["schema"] == "wan2gp-wanflow-ui"
    assert payload["graph"]["nodes"]

    imported = client.post("/api/workflow/import", json={"graph": payload["graph"], "name": "imported copy"})
    assert imported.status_code == 200, imported.text
    assert imported.json()["node_count"] == len(payload["graph"]["nodes"])

    cleanup = client.delete("/api/workflow/workflows/imported-copy")
    assert cleanup.status_code == 200
