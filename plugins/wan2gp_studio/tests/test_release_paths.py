"""Model release paths on workflow run completion (P0/P1 from the v4 audits).

A failed or cancelled run must not leave a stale model in VRAM: the run
worker releases unconditionally on those outcomes, while a completed run
honors the graph's unload flags.

The tests drive the REAL state machine: nodes start "queued" and the stub
runner fires node_callback("running") exactly like the WanFlow runner does,
so the release decision is exercised against the actual queued → running →
error/cancelled sequences instead of a pre-populated snapshot.
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

GENERATION_GRAPH = {
    "name": "T",
    "nodes": [{"id": "g1", "type": "generate_video", "params": {"model_type": "wan2.1"}, "enabled": True}],
    "edges": [],
}


class _StubRunner:
    def __init__(self, fail: bool = False, cancel: bool = False, fire_node_events: bool = True):
        self.fail = fail
        self.cancel = cancel
        self.fire_node_events = fire_node_events
        self.calls: list[str] = []
        self._node_callback = None

    def run_graph(self, host, session, variables, graph, inputs, node_callback=None, **kwargs):
        self._node_callback = node_callback
        if self.fire_node_events:
            node_callback("g1", "running", None)  # real queued → running transition
        if self.fail:
            raise RuntimeError("boom mid-run")
        if self.cancel:
            raise InterruptedError()
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
        # the real run() seeds "queued"/"skipped"; the worker and callbacks own
        # every transition from here
        "nodes": {node["id"]: "queued" for node in graph.get("nodes") or []},
        "outputs": [], "variables": {}, "errors": [],
        "generation_started": False,
        "cancel_requested": False, "created_at": time.time(), "updated_at": time.time(),
        "events": deque(maxlen=10), "next_event": 1,
    }
    compat._runs["test-run"] = record
    compat._run_worker(record, graph, [], runner)
    return record, host, runner


def test_failed_generation_run_releases_models_unconditionally(tmp_path):
    record, host, runner = _run_worker_once(tmp_path, GENERATION_GRAPH, _StubRunner(fail=True))
    assert record["status"] == "failed"
    assert record["nodes"]["g1"] == "error"  # terminal state, NOT "running"/"done"
    assert record["generation_started"] is True
    assert runner.calls == ["always"]
    assert host.released == 1


def test_cancelled_generation_run_releases_models_unconditionally(tmp_path):
    record, host, runner = _run_worker_once(tmp_path, GENERATION_GRAPH, _StubRunner(cancel=True))
    assert record["status"] == "cancelled"
    assert record["nodes"]["g1"] == "cancelled"
    assert record["generation_started"] is True
    assert runner.calls == ["always"]
    assert host.released == 1


def test_failure_before_generation_starts_does_not_release(tmp_path):
    """run_graph raises before any node runs: nothing to unload (no model was
    ever loaded), and the honoring releaser must not fire either."""
    runner = _StubRunner(fail=True, fire_node_events=False)
    record, host, runner = _run_worker_once(tmp_path, GENERATION_GRAPH, runner)
    assert record["status"] == "failed"
    assert record["generation_started"] is False
    assert runner.calls == []
    assert host.released == 0


def test_successful_run_honors_unload_flags(tmp_path):
    record, host, runner = _run_worker_once(tmp_path, GENERATION_GRAPH, _StubRunner(fail=False))
    assert record["status"] == "completed"
    # no unload flags in the graph: the honoring releaser stays silent
    assert runner.calls == []
    assert host.released == 0


def test_no_release_while_another_run_is_active(tmp_path):
    """A failing run must not pull the model out from under a concurrent run."""
    host = _Host()
    compat = WorkflowCompat(
        host, plugins_root=str(Path(temp_dir := f"{tmp_path}") / "plugins"), output_root=Path(temp_dir) / "workflow_outputs"
    )
    other = {"id": "other-run", "status": "running", "nodes": {}, "generation_started": True,
             "events": deque(maxlen=10), "next_event": 1, "cancel_requested": False, "errors": []}
    compat._runs["other-run"] = other
    record = {
        "id": "test-run", "status": "running", "progress": 0, "message": "",
        "nodes": {"g1": "queued"},
        "outputs": [], "variables": {}, "errors": [],
        "generation_started": False,
        "cancel_requested": False, "created_at": time.time(), "updated_at": time.time(),
        "events": deque(maxlen=10), "next_event": 1,
    }
    compat._runs["test-run"] = record
    runner = _StubRunner(fail=True)
    compat._run_worker(record, GENERATION_GRAPH, [], runner)
    assert record["status"] == "failed"
    assert runner.calls == []  # another run holds the model: no release
    assert host.released == 0
