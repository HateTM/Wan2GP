"""Model release paths on workflow run completion (P0 from the v4 audit).

A failed or cancelled run must not leave a stale model in VRAM: the run
worker releases unconditionally on those outcomes, while a completed run
honors the graph's unload flags.
"""
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

from fastapi.testclient import TestClient  # noqa: E402

from wan2gp_studio.plugin import WanGPStudioPlugin  # noqa: E402
from wan2gp_studio.workflow_compat import WorkflowCompat  # noqa: E402


class _StubRunner:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls: list[str] = []

    def run_graph(self, *args, **kwargs):
        if self.fail:
            raise RuntimeError("boom mid-run")
        return [], {}

    def release_workflow_models(self, plugin, graph):
        # the real helper only fires when the graph's unload flags are set
        flags = (graph.get("settings") or {}).get("unload_on_model_change")
        if flags:
            self.calls.append("honoring")
            self._release(plugin)

    def release_loaded_model(self, plugin):
        self.calls.append("always")
        self._release(plugin)

    @staticmethod
    def _release(plugin):
        release = getattr(plugin, "release_model", None)
        if callable(release):
            release()


class _Host:
    def __init__(self):
        self.released = 0

    def get_session(self):
        return {"_ui_local": None}

    def release_model(self):
        self.released += 1


def _run_worker_once(tmp_path, graph, runner):
    host = _Host()
    compat = WorkflowCompat(
        host, plugins_root=str(tmp_path / "plugins"), output_root=tmp_path / "workflow_outputs"
    )
    record = {
        "id": "test-run", "status": "running", "progress": 0, "message": "",
        # node states as run() would populate them from the graph
        "nodes": {node["id"]: "done" for node in graph.get("nodes") or []},
        "outputs": [], "variables": {}, "errors": [],
        "cancel_requested": False, "created_at": time.time(), "updated_at": time.time(),
        "events": deque(maxlen=10), "next_event": 1,
    }
    compat._run_worker(record, graph, [], runner)
    return record, host, runner


def test_failed_run_releases_models_unconditionally(tmp_path):
    graph = {
        "name": "T",
        "nodes": [{"id": "g1", "type": "generate_video", "params": {"model_type": "wan2.1"}, "enabled": True}],
        "edges": [],
    }
    record, host, runner = _run_worker_once(tmp_path, graph, _StubRunner(fail=True))
    assert record["status"] == "failed"
    assert runner.calls == ["always"]
    assert host.released == 1


def test_cancelled_run_releases_models_unconditionally(tmp_path):
    graph = {
        "name": "T",
        "nodes": [{"id": "g1", "type": "generate_video", "params": {"model_type": "wan2.1"}, "enabled": True}],
        "edges": [],
    }
    runner = _StubRunner(fail=False)

    def raise_interrupted(*args, **kwargs):
        raise InterruptedError()

    runner.run_graph = raise_interrupted
    record, host, runner = _run_worker_once(tmp_path, graph, runner)
    assert record["status"] == "cancelled"
    assert runner.calls == ["always"]
    assert host.released == 1


def test_successful_run_honors_unload_flags(tmp_path):
    graph = {
        "name": "T",
        "nodes": [{"id": "g1", "type": "generate_video", "params": {"model_type": "wan2.1"}, "enabled": True}],
        "edges": [],
    }
    record, host, runner = _run_worker_once(tmp_path, graph, _StubRunner(fail=False))
    assert record["status"] == "completed"
    # no unload flags in the graph: the honoring releaser stays silent
    assert runner.calls == []
    assert host.released == 0
