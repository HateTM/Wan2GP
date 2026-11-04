import importlib
import json
import os
import re
import sys
from pathlib import Path

import pytest


TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT)
sys.path.insert(0, PLUGINS_ROOT)
sys.path.insert(0, REPO_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from wan2gp_studio.plugin import WanGPStudioPlugin  # noqa: E402
from wan2gp_studio.workflow_compat import WorkflowCompat  # noqa: E402

GRAPH_MODEL = None
try:
    GRAPH_MODEL = importlib.import_module("wan2gp-wanflow-ui.graph_model")
except Exception:  # optional plugin is absent in clean checkouts / CI
    GRAPH_MODEL = None


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
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def slug(value):
        return re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "block")).strip("-_").lower()[:80] or "block"

    def save_group(self, graph, group_id, name=None):
        group = next((item for item in graph.get("groups") or [] if item.get("id") == group_id), None)
        if not group:
            raise ValueError("The selected group does not exist.")
        title = str(name or group.get("title") or "Reusable block")
        payload = {"schema": "wan2gp-wanflow-block-v1", "name": title, "nodes": [], "edges": [], "groups": [group]}
        path = self.root / f"{self.slug(title)}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def delete(self, block_id):
        path = self.root / f"{self.slug(block_id)}.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        path.unlink()
        return path

    def catalog(self):
        out = []
        for path in sorted(self.root.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            out.append({"id": path.stem, "name": data.get("name") or path.stem})
        return out


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
    if GRAPH_MODEL is None:
        pytest.skip("wanflow-ui not installed")
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
    if GRAPH_MODEL is None:
        pytest.skip("wanflow-ui not installed")
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
    if GRAPH_MODEL is None:
        pytest.skip("wanflow-ui not installed")
    compat = _compat(tmp_path)
    graph = {"name": "Unknown", "nodes": [{"id": "u1", "type": "mystery_node", "params": {"x": 1}, "enabled": True}], "edges": []}
    imported = compat.import_workflow(graph)
    assert imported["unknown_nodes"] == ["mystery_node"]
    stored = compat.load(imported["id"])
    assert stored["nodes"][0]["type"] == "mystery_node"


def test_comfyui_payload_imports_as_opaque(tmp_path):
    if GRAPH_MODEL is None:
        pytest.skip("wanflow-ui not installed")
    compat = _compat(tmp_path)
    imported = compat.import_workflow({
        "1": {"class_type": "KSampler", "inputs": {"seed": 1, "model": ["5", 0]}},
        "5": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "m.safetensors"}},
    })
    assert imported["id"] == "comfyui-import"
    assert imported["unknown_nodes"] == ["comfyui_node"]
    stored = compat.load("comfyui-import")
    assert [node["type"] for node in stored["nodes"]] == ["comfyui_node", "comfyui_node"]
    sampler = [node for node in stored["nodes"] if node["params"]["comfyui"]["key"] == "1"][0]
    assert sampler["params"]["comfyui"]["inputs"]["model"] == ["5", 0]

    exported = compat.export_workflow(imported["id"], fmt="comfyui")
    assert set(exported["prompt"].keys()) == {"1", "5"}
    assert exported["prompt"]["1"]["inputs"]["model"] == ["5", 0]


def test_version_gate_and_disabled_state(tmp_path):
    plugins_root = tmp_path / "plugins"
    plugin_dir = plugins_root / "wan2gp-wanflow-ui"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text("# stub", encoding="utf-8")
    (plugin_dir / "plugin_info.json").write_text(json.dumps({"version": "0.0.9"}), encoding="utf-8")

    outdated = WorkflowCompat(StubHost(), plugins_root=plugins_root, min_version="0.1.0")
    assert outdated.state() == "incompatible"
    assert outdated.available() is False

    disabled = WorkflowCompat(StubHost(), plugins_root=plugins_root, enabled_provider=lambda: False)
    assert disabled.state() == "disabled"
    assert disabled.available() is False

    current = WorkflowCompat(StubHost(), plugins_root=plugins_root, min_version="0.0.1")
    assert current.state() == "available"


def _ui_payload():
    return {
        "last_node_id": 2, "last_link_id": 1, "version": 0.4,
        "nodes": [
            {"id": 1, "type": "CheckpointLoaderSimple", "pos": [100, 100], "mode": 0,
             "inputs": [], "outputs": [{"name": "MODEL", "type": "MODEL", "links": [1]}],
             "properties": {}, "widgets_values": ["model.safetensors"]},
            {"id": 2, "type": "KSampler", "pos": [400, 100], "mode": 0,
             "inputs": [{"name": "model", "type": "MODEL", "link": 1}], "outputs": [],
             "properties": {}, "widgets_values": [123, "fixed", 8]},
        ],
        "links": [[1, 1, 0, 2, 0, "MODEL"]],
    }


def test_comfyui_ui_import_preserves_layout_and_values(tmp_path):
    if GRAPH_MODEL is None:
        pytest.skip("wanflow-ui not installed")
    compat = _compat(tmp_path)
    imported = compat.import_workflow(_ui_payload())
    assert imported["id"] == "comfyui-ui-import"
    assert imported["unknown_nodes"] == ["comfyui_node"]
    stored = compat.load(imported["id"])
    by_id = {node["id"]: node for node in stored["nodes"]}
    assert by_id["c1"]["position"] == {"x": 100.0, "y": 100.0}
    assert by_id["c2"]["params"]["comfyui"]["widgets_values"] == [123, "fixed", 8]
    edge = stored["edges"][0]
    assert edge["source"]["node"] == "c1" and edge["target"]["node"] == "c2"
    assert edge["type"] == "MODEL"


def test_comfyui_ui_export_round_trip(tmp_path):
    if GRAPH_MODEL is None:
        pytest.skip("wanflow-ui not installed")
    compat = _compat(tmp_path)
    imported = compat.import_workflow(_ui_payload())
    exported = compat.export_workflow(imported["id"], fmt="comfyui-ui")
    assert exported["format"] == "comfyui-ui"
    assert exported["links"] == _ui_payload()["links"]
    by_id = {node["id"]: node for node in exported["nodes"]}
    assert by_id[1]["widgets_values"] == ["model.safetensors"]
    assert by_id[2]["inputs"][0]["link"] == 1
    assert by_id[2]["pos"] == [400, 100]


def test_comfyui_ui_export_survives_edits(tmp_path):
    """Import → Move node → Delete node → Save → Export: layout edit wins and
    links are rebuilt from the live graph, so nothing dangles."""
    if GRAPH_MODEL is None:
        pytest.skip("wanflow-ui not installed")
    compat = _compat(tmp_path)
    imported = compat.import_workflow(_ui_payload())
    graph = compat.load(imported["id"])

    # move the sampler on the canvas and drop the loader node
    for node in graph["nodes"]:
        if node["id"] == "c2":
            node["position"] = {"x": 650, "y": 240}
    graph["nodes"] = [node for node in graph["nodes"] if node["id"] != "c1"]
    graph["edges"] = []
    compat.save(graph, imported["name"])

    exported = compat.export_workflow(imported["id"], fmt="comfyui-ui")
    assert [spec["id"] for spec in exported["nodes"]] == [2]
    sampler = exported["nodes"][0]
    assert sampler["pos"] == [650, 240]
    assert sampler["inputs"][0]["link"] is None
    assert exported["links"] == []
    assert exported["last_link_id"] == 1  # never shrinks below the original ids
    assert exported["version"] == 0.4


def test_comfyui_ui_export_rebuilds_links_from_edges(tmp_path):
    """An unchanged connection keeps its link id; re-wiring allocates a new one."""
    if GRAPH_MODEL is None:
        pytest.skip("wanflow-ui not installed")
    compat = _compat(tmp_path)
    imported = compat.import_workflow(_ui_payload())

    graph = compat.load(imported["id"])
    compat.save(graph, imported["name"])
    exported = compat.export_workflow(imported["id"], fmt="comfyui-ui")
    assert exported["links"] == [[1, 1, 0, 2, 0, "MODEL"]]

    graph = compat.load(imported["id"])
    graph["edges"][0]["type"] = "CONDITIONING"
    compat.save(graph, imported["name"])
    exported = compat.export_workflow(imported["id"], fmt="comfyui-ui")
    assert exported["links"] == [[2, 1, 0, 2, 0, "CONDITIONING"]]
    by_id = {node["id"]: node for node in exported["nodes"]}
    assert by_id[1]["outputs"][0]["links"] == [2]
    assert by_id[2]["inputs"][0]["link"] == 2
    assert exported["last_link_id"] == 2


def test_comfyui_ui_metadata_lives_on_the_graph(tmp_path):
    """Canvas metadata is stored once per workflow, not copied into every node."""
    if GRAPH_MODEL is None:
        pytest.skip("wanflow-ui not installed")
    compat = _compat(tmp_path)
    imported = compat.import_workflow(_ui_payload())
    graph = compat.load(imported["id"])
    assert graph["ui"]["comfyui_ui"]["links"] == _ui_payload()["links"]
    for node in graph["nodes"]:
        assert "ui_meta" not in node["params"].get("comfyui", {})


def test_comfyui_ui_export_reads_legacy_per_node_metadata(tmp_path):
    """Workflows saved before the ui_meta move still export with their links."""
    if GRAPH_MODEL is None:
        pytest.skip("wanflow-ui not installed")
    compat = _compat(tmp_path)
    imported = compat.import_workflow(_ui_payload())
    graph = compat.load(imported["id"])
    ui_meta = graph["ui"].pop("comfyui_ui")
    for node in graph["nodes"]:
        node["params"]["comfyui"]["ui_meta"] = ui_meta
    compat.save(graph, imported["name"])
    exported = compat.export_workflow(imported["id"], fmt="comfyui-ui")
    assert exported["links"] == [[1, 1, 0, 2, 0, "MODEL"]]
    assert exported["nodes"][1]["inputs"][0]["link"] == 1


def test_save_block_and_delete_block_api(tmp_path):
    if GRAPH_MODEL is None:
        pytest.skip("wanflow-ui not installed")
    compat = _compat(tmp_path)
    graph = {
        "name": "Blocks",
        "nodes": [
            {"id": "n1", "type": "text_prompt", "params": {}, "enabled": True},
            {"id": "n2", "type": "text_prompt", "params": {}, "enabled": True},
        ],
        "edges": [],
        "groups": [{"id": "grp1", "title": "My Block", "node_ids": ["n1", "n2"]}],
        "ui": {"selected_group_id": "grp1"},
    }
    saved = compat.save_block(graph)
    assert saved == {"id": "my-block", "name": "My Block"}
    assert compat.catalog()["blocks"] == [{"id": "my-block", "name": "My Block"}]

    with pytest.raises(ValueError):
        compat.save_block({"name": "No group selected"})
    with pytest.raises(KeyError):
        compat.delete_block("missing-block")

    compat.delete_block("my-block")
    assert compat.catalog()["blocks"] == []


def test_export_import_routes_against_installed_plugin(tmp_path, monkeypatch):
    plugin = WanGPStudioPlugin()
    plugin.server_config = {
        "image_save_path": str(tmp_path / "images"),
        "save_path": str(tmp_path / "videos"),
        "audio_save_path": str(tmp_path / "audio"),
    }
    client = TestClient(plugin.create_web_app())

    if not os.path.isfile(os.path.join(PLUGINS_ROOT, "wan2gp-wanflow-ui", "plugin.py")):
        pytest.skip("wanflow-ui not installed")

    # Build the workflow through the real import route instead of assuming a
    # user-created workflow exists: the vendored checkout ships none (the
    # fork's .gitignore excludes workflows/* as runtime data).
    created = client.post("/api/workflow/import", json={
        "name": "selftest t2v",
        "graph": {
            "name": "Selftest T2V",
            "nodes": [{"id": "n1", "type": "text_prompt", "params": {"text": "hi"}, "enabled": True}],
            "edges": [],
        },
    })
    assert created.status_code == 200, created.text
    slug = created.json()["id"]

    exported = client.get(f"/api/workflow/workflows/{slug}/export")
    assert exported.status_code == 200, exported.text
    payload = exported.json()
    assert payload["schema"] == "wan2gp-wanflow-ui"
    assert payload["graph"]["nodes"]

    imported = client.post("/api/workflow/import", json={"graph": payload["graph"], "name": "selftest copy"})
    assert imported.status_code == 200, imported.text
    assert imported.json()["node_count"] == len(payload["graph"]["nodes"])

    for leftover in (imported.json()["id"], slug):
        cleanup = client.delete(f"/api/workflow/workflows/{leftover}")
        assert cleanup.status_code == 200, cleanup.text
