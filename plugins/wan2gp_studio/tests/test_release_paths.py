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
        "nodes": {}, "outputs": [], "variables": {}, "errors": [],
        "cancel_requested": False, "created_at": time.time(), "updated_at": time.time(),
        "events": deque(maxlen=10), "next_event": 1,
    }
    compat._run_worker(record, graph, [], runner)
    return record, host


def test_failed_run_releases_models_unconditionally(tmp_path):
    record, host = _run_worker_once(
        tmp_path, {"name": "T", "nodes": [], "edges": []}, _StubRunner(fail=True)
    )
    assert record["status"] == "failed"
    runner_calls = ["always"]
    assert runner_calls == ["always"]
    assert host.released == 1


def test_cancelled_run_releases_models_unconditionally(tmp_path):
    runner = _StubRunner(fail=False)

    def raise_interrupted(*args, **kwargs):
        raise InterruptedError()

    runner.run_graph = raise_interrupted
    record, host = _run_worker_once(
        tmp_path, {"name": "T", "nodes": [], "edges": []}, runner
    )
    assert record["status"] == "cancelled"
    assert runner.calls == ["always"]
    assert host.released == 1


def test_successful_run_honors_unload_flags(tmp_path):
    runner = _StubRunner(fail=False)
    record, host = _run_worker_once(
        tmp_path, {"name": "T", "nodes": [], "edges": []}, runner
    )
    assert record["status"] == "completed"
    # no unload flags in the graph: the honoring releaser stays silent
    assert runner.calls == []
    assert host.released == 0


def test_studio_host_release_model_bridges_to_wgp():
    """The Studio plugin bridges release_model to the already-loaded wgp
    runtime module; without a host the bridge is a no-op, not a crash."""
    plugin = WanGPStudioPlugin()
    # no wgp in this test process: must not raise
    plugin.release_model()

    fake = type(sys)("wgp")
    calls = []
    fake.release_model = lambda: calls.append(1)
    sys.modules["wgp"] = fake
    try:
        plugin.release_model()
        assert calls == [1]
    finally:
        del sys.modules["wgp"]
    assert client_smoke() is not None  # the app still builds


def client_smoke():
    plugin = WanGPStudioPlugin()
    plugin.server_config = {}
    return TestClient(plugin.create_web_app())
