from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]

sys.path.insert(0, str(REPO))

_package = types.ModuleType("wanflow_ui_test_pkg")
_package.__path__ = [str(ROOT)]
sys.modules.setdefault("wanflow_ui_test_pkg", _package)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"wanflow_ui_test_pkg.{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"wanflow_ui_test_pkg.{name}"] = module
    spec.loader.exec_module(module)
    return module


graph_runner = _load("graph_runner")
graph_model = _load("graph_model")


class _Artifact:
    def __init__(self, path: str):
        self.path = path


class _Result:
    def __init__(self, path: str):
        self.cancelled = False
        self.success = True
        self.errors: list[str] = []
        self.artifacts = [_Artifact(path)]
        self.generated_files: list[str] = []


class _Job:
    def __init__(self, path: str):
        self._path = path
        self.done = True

    def result(self):
        return _Result(self._path)

    def cancel(self):
        pass


class _StubAPI:
    def __init__(self, path: str):
        self._path = path

    def submit_task(self, settings, callbacks=None):
        return _Job(self._path)

    def submit_media_postprocessing(self, source, **kwargs):
        return _Job(self._path)


class _StubPlugin:
    def __init__(self):
        self.release_calls = 0

    def release_model(self):
        self.release_calls += 1

    def list_model_defs(self):
        return [
            {"model_type": "model_a", "metadata": {"outputs": ["video"]}},
            {"model_type": "model_b", "metadata": {"outputs": ["video"]}},
        ]

    def get_model_def(self, model_type):
        return {"base_model_type": "test", "vae_block_size": 16}

    def get_default_settings(self, model_type):
        return {}

    def get_model_family(self, model_type, for_ui=True):
        return "test"

    def get_resolution_choices(self, resolution, model_def):
        return [("720p", "720x1280")], None


def _generation_node(node_id: str, model_type: str, media: str = "video") -> dict:
    node_type = f"generate_{media}"
    node = graph_model.new_node(node_type, f"Gen {node_id}")
    node["id"] = node_id
    node["params"] = {"model_type": model_type}
    return node


def _ai_node() -> dict:
    node = graph_model.new_node("ai_analyze", "AI Analyze")
    return node


def _run(plugin, graph):
    return graph_runner.run_graph(plugin, _StubAPI(""), {}, graph, [], output_root=ROOT / "tests" / "tmp_out")


class WorkflowUnloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        self.tmp.close()
        # these tests assert model loading/unloading, so every node has to really run
        self._previous_cache_switch = os.environ.get("WANFLOW_NO_CACHE")
        os.environ["WANFLOW_NO_CACHE"] = "1"

    def tearDown(self):
        Path(self.tmp.name).unlink(missing_ok=True)
        if self._previous_cache_switch is None:
            os.environ.pop("WANFLOW_NO_CACHE", None)
        else:
            os.environ["WANFLOW_NO_CACHE"] = self._previous_cache_switch

    def _graph(self, nodes: list[dict], unload: bool) -> dict:
        graph = graph_model.new_graph()
        graph["nodes"] = nodes
        graph["settings"] = {"aspect_ratio": "source", "unload_on_model_change": unload}
        return graph

    def test_same_model_generations_do_not_release_between_nodes(self):
        plugin = _StubPlugin()
        graph = self._graph([
            _generation_node("a", "model_a"),
            _generation_node("b", "model_a"),
        ], unload=True)
        _run(plugin, graph)
        self.assertEqual(plugin.release_calls, 0)
        graph_runner.release_workflow_models(plugin, graph)
        self.assertEqual(plugin.release_calls, 1)

    def test_model_change_releases_between_generations_and_at_end(self):
        plugin = _StubPlugin()
        graph = self._graph([
            _generation_node("a", "model_a"),
            _generation_node("b", "model_b"),
        ], unload=True)
        _run(plugin, graph)
        self.assertEqual(plugin.release_calls, 1)
        graph_runner.release_workflow_models(plugin, graph)
        self.assertEqual(plugin.release_calls, 2)

    def test_aux_node_releases_resident_model(self):
        plugin = _StubPlugin()
        graph = self._graph([
            _generation_node("a", "model_a"),
            _ai_node(),
        ], unload=True)
        with self.assertRaises(RuntimeError):
            # The AI runtime is unavailable in tests; the release must happen
            # before the node dispatch raises.
            _run(plugin, graph)
        self.assertEqual(plugin.release_calls, 1)

    def test_flags_off_never_releases(self):
        plugin = _StubPlugin()
        graph = self._graph([
            _generation_node("a", "model_a"),
            _generation_node("b", "model_b"),
            _ai_node(),
        ], unload=False)
        with self.assertRaises(RuntimeError):
            _run(plugin, graph)
        self.assertEqual(plugin.release_calls, 0)
        graph_runner.release_workflow_models(plugin, graph)
        self.assertEqual(plugin.release_calls, 0)


if __name__ == "__main__":
    unittest.main()
