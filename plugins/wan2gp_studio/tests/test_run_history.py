"""Unified task registry persistence (audit P1): terminal workflow runs are
mirrored to disk through the run_finished_callback so the Queue survives
restarts, mirroring the generation job history."""
import json
import os
import sys
import time
from collections import deque
from pathlib import Path

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT)
sys.path.insert(0, PLUGINS_ROOT)
sys.path.insert(0, REPO_ROOT)

from wan2gp_studio.workflow_compat import WorkflowCompat  # noqa: E402

GRAPH = {
    "name": "Persist test",
    "nodes": [{"id": "g1", "type": "generate_video", "params": {"model_type": "wan2.1"}, "enabled": True}],
    "edges": [],
}


class _Host:
    def get_session(self):
        return {"_ui_local": None}


class _Runner:
    def run_graph(self, host, session, variables, graph, inputs, node_callback=None, **kwargs):
        node_callback("g1", "running", None)
        raise RuntimeError("boom")


def test_terminal_run_reaches_persistence_callback(tmp_path):
    persisted: list[dict] = []
    compat = WorkflowCompat(
        _Host(),
        plugins_root=str(tmp_path / "plugins"),
        output_root=tmp_path / "workflow_outputs",
        run_finished_callback=persisted.append,
    )
    record = {
        "id": "run-1", "status": "running", "progress": 0, "message": "",
        "nodes": {"g1": "queued"},
        "outputs": [], "variables": {}, "errors": [],
        "generation_started": False,
        "cancel_requested": False, "created_at": time.time(), "updated_at": time.time(),
        "events": deque(maxlen=10), "next_event": 1,
        "graph_name": "Persist test", "graph": GRAPH,
    }
    compat._runs["run-1"] = record
    compat._run_worker(record, GRAPH, [], _Runner())
    assert record["status"] == "failed"
    assert len(persisted) == 1
    compact = persisted[0]
    assert compact["kind"] == "workflow"
    assert compact["status"] == "failed"
    assert compact["name"] == "Persist test"
    assert compact["generation_started"] is True
    assert compact["graph"] == GRAPH  # the Queue can restore the graph later


def test_all_runs_reports_active_and_terminal(tmp_path):
    compat = WorkflowCompat(
        _Host(), plugins_root=str(tmp_path / "plugins"), output_root=tmp_path / "workflow_outputs"
    )
    record = {
        "id": "run-2", "status": "running", "progress": 12, "message": "Running",
        "nodes": {}, "outputs": [], "variables": {}, "errors": [],
        "generation_started": False,
        "cancel_requested": False, "created_at": time.time(), "updated_at": time.time(),
        "events": deque(maxlen=10), "next_event": 1,
        "graph_name": "Live", "graph": GRAPH,
    }
    compat._runs["run-2"] = record
    compat._run_order.append("run-2")
    runs = compat.all_runs()
    assert len(runs) == 1
    assert runs[0]["id"] == "run-2"
    assert runs[0]["status"] == "running"
