import json
import os
import sys
import time
from pathlib import Path

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT)
sys.path.insert(0, PLUGINS_ROOT)
sys.path.insert(0, REPO_ROOT)

import pytest  # noqa: E402

from wan2gp_studio import workflow_compat  # noqa: E402
from wan2gp_studio.workflow_compat import WorkflowCompat, WorkflowLimitError  # noqa: E402

GRAPH_MODEL = None
try:
    GRAPH_MODEL = __import__("wan2gp-wanflow-ui.graph_model", fromlist=["graph_model"])
except Exception:
    GRAPH_MODEL = None


class StubGraphStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def choices(self):
        return []

    def save(self, graph, name):
        path = self.root / "saved.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        return graph, path

    def load(self, slug):
        raise FileNotFoundError(slug)

    def delete(self, slug):
        pass


class StubBlockStore:
    def __init__(self, root):
        self.root = Path(root)

    def catalog(self):
        return []


class StubNodeRegistry:
    @staticmethod
    def build_catalog(model_defs, processes, loras, resolver):
        return {"nodes": [{"type": "text_prompt"}], "models": [], "processes": [], "loras": {}}


class StubGraphRunner:
    @staticmethod
    def run_graph(plugin, session, state, graph, inputs, *, output_root, callback=None, cancel_check=None, node_callback=None):
        deadline = time.time() + 30
        while time.time() < deadline:
            if cancel_check and cancel_check():
                raise InterruptedError("Cancelled")
            time.sleep(0.05)
        return [], {}

    @staticmethod
    def release_workflow_models(plugin, graph):
        pass


class StubHost:
    def list_model_defs(self):
        return []

    def get_session(self):
        return None


def _loader():
    store_module = type("M", (), {"GraphStore": StubGraphStore})
    block_module = type("M", (), {"BlockStore": StubBlockStore})
    registry_module = type("M", (), {"build_catalog": staticmethod(StubNodeRegistry.build_catalog)})
    return {
        "graph_model": GRAPH_MODEL,
        "graph_store": store_module,
        "block_store": block_module,
        "node_registry": registry_module,
        "graph_runner": StubGraphRunner,
    }


def _graph():
    node = {"id": "n1", "type": "text_prompt", "params": {}, "enabled": True}
    if GRAPH_MODEL is not None:
        return GRAPH_MODEL.new_graph("Hardening") | {"nodes": [node], "edges": []}
    return {"name": "Hardening", "nodes": [node], "edges": []}


requires_graph_model = pytest.mark.skipif(GRAPH_MODEL is None, reason="wanflow-ui not installed")


@requires_graph_model
def test_active_run_limit(tmp_path):
    compat = WorkflowCompat(StubHost(), plugins_root=tmp_path / "plugins", loader=_loader, output_root=tmp_path / "out")
    limit = workflow_compat.MAX_ACTIVE_RUNS
    runs = []
    for _ in range(limit):
        runs.append(compat.start_run(_graph())["run_id"])
    with pytest.raises(WorkflowLimitError):
        compat.start_run(_graph())
    for run_id in runs:
        compat.cancel(run_id)
    deadline = time.time() + 10
    while time.time() < deadline:
        if all(compat.snapshot(run_id)["status"] in ("completed", "failed", "cancelled") for run_id in runs):
            break
        time.sleep(0.05)
    started = compat.start_run(_graph())
    assert started["run_id"]


@requires_graph_model
def test_prune_keeps_active_and_drops_expired_terminal(tmp_path):
    compat = WorkflowCompat(StubHost(), plugins_root=tmp_path / "plugins", loader=_loader, output_root=tmp_path / "out")
    now = time.time()
    compat._run_order = ["active1", "old", "fresh"]
    compat._runs = {
        "active1": {"status": "running", "updated_at": now - 999999},
        "old": {"status": "completed", "updated_at": now - workflow_compat.TERMINAL_RUN_TTL_SECONDS - 10},
        "fresh": {"status": "completed", "updated_at": now},
    }
    compat._prune_runs()
    assert set(compat._runs) == {"active1", "fresh"}
    assert compat._run_order == ["active1", "fresh"]


@requires_graph_model
def test_terminal_history_is_capped(tmp_path):
    compat = WorkflowCompat(StubHost(), plugins_root=tmp_path / "plugins", loader=_loader, output_root=tmp_path / "out")
    now = time.time()
    compat._run_order = []
    compat._runs = {}
    for index in range(workflow_compat.MAX_TERMINAL_RUNS + 5):
        run_id = f"t{index}"
        compat._run_order.append(run_id)
        compat._runs[run_id] = {"status": "completed", "updated_at": now}
    compat._prune_runs()
    assert len(compat._runs) == workflow_compat.MAX_TERMINAL_RUNS
    assert compat._run_order[0] == "t5"
