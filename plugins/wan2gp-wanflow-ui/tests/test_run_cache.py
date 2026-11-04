from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

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


run_cache = _load("run_cache")
graph_runner = _load("graph_runner")
graph_model = _load("graph_model")


class _StubPlugin:
    def release_model(self):
        pass

    def list_model_defs(self):
        return [{"model_type": "model_a", "metadata": {"outputs": ["video"]}}]

    def get_model_def(self, model_type):
        return {"base_model_type": "test", "vae_block_size": 16}

    def get_default_settings(self, model_type):
        return {}

    def get_model_family(self, model_type, for_ui=True):
        return "test"

    def get_resolution_choices(self, resolution, model_def):
        return [("720p", "720x1280")], None


class RunCacheTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.out = self.tmp / "out"
        self.gen_calls = 0
        self.resize_calls = 0
        self.resize_fail_once = False
        os.environ.pop("WANFLOW_NO_CACHE", None)

    def tearDown(self):
        os.environ.pop("WANFLOW_NO_CACHE", None)
        self._tmp.cleanup()

    # -- stubs ---------------------------------------------------------------------------------
    def _fake_generation(self, *_args, **_kwargs):
        self.gen_calls += 1
        path = self.tmp / f"gen-{self.gen_calls}.mp4"
        path.write_bytes(b"video" + bytes([self.gen_calls]))
        return str(path)

    def _fake_resize(self, source, width, height, output, cancel_check=None):
        self.resize_calls += 1
        if self.resize_fail_once:
            self.resize_fail_once = False
            raise RuntimeError("simulated failure")
        Path(output).write_bytes(Path(source).read_bytes() + b"-resized")
        return str(output)

    def _graph(self, seed: int = -1, gen_params: dict | None = None) -> dict:
        graph = graph_model.new_graph()
        gen = graph_model.new_node("generate_video", "Gen")
        gen["id"] = "gen"
        gen["params"] = {"model_type": "model_a", "seed": seed, **(gen_params or {})}
        resize = graph_model.new_node("ffmpeg_resize", "Resize")
        resize["id"] = "rs"
        resize["params"] = {"width": 320, "height": 180}
        graph["nodes"] = [gen, resize]
        graph["edges"] = [{"id": "e1", "source": {"node": "gen", "port": "output"}, "target": {"node": "rs", "port": "video"}, "type": "VIDEO"}]
        graph["settings"] = {"aspect_ratio": "source"}
        return graph

    def _run(self, graph):
        with mock.patch.object(graph_runner, "_submit_generation", self._fake_generation), \
                mock.patch.object(graph_runner.media_ops, "resize", self._fake_resize):
            return graph_runner.run_graph(_StubPlugin(), None, {}, graph, [], output_root=self.out)

    # -- tests ---------------------------------------------------------------------------------
    def test_fixed_seed_is_reused_across_runs(self):
        graph = self._graph(seed=7)
        first, _ = self._run(graph)
        second, _ = self._run(graph)
        self.assertEqual((self.gen_calls, self.resize_calls), (1, 1))
        self.assertEqual(first, second)

    def test_random_seed_regenerates_after_a_successful_run(self):
        graph = self._graph(seed=-1)
        self._run(graph)
        self._run(graph)
        self.assertEqual(self.gen_calls, 2)
        self.assertEqual(self.resize_calls, 2)

    def test_failed_run_resumes_without_regenerating_even_with_random_seed(self):
        graph = self._graph(seed=-1)
        self.resize_fail_once = True
        with self.assertRaises(RuntimeError):
            self._run(graph)
        outputs, _ = self._run(graph)
        self.assertEqual(self.gen_calls, 1, "the generation finished before the failure and must be reused")
        self.assertEqual(self.resize_calls, 2)
        self.assertTrue(outputs)
        # the checkpoint is gone after the successful run
        self._run(graph)
        self.assertEqual(self.gen_calls, 2)

    def test_changing_a_parameter_invalidates_the_node_and_everything_below(self):
        self._run(self._graph(seed=7))
        self._run(self._graph(seed=8))
        self.assertEqual((self.gen_calls, self.resize_calls), (2, 2))

    def test_changing_only_a_downstream_parameter_keeps_the_generation(self):
        graph = self._graph(seed=7)
        self._run(graph)
        graph["nodes"][1]["params"]["width"] = 640
        self._run(graph)
        self.assertEqual((self.gen_calls, self.resize_calls), (1, 2))

    def test_missing_output_file_is_regenerated(self):
        graph = self._graph(seed=7)
        first, _ = self._run(graph)
        for path in first:
            Path(path).unlink()
        self._run(graph)
        self.assertEqual(self.gen_calls, 2)

    def test_node_can_opt_out(self):
        graph = self._graph(seed=7, gen_params={"cache": False})
        self._run(graph)
        self._run(graph)
        self.assertEqual(self.gen_calls, 2)
        self.assertEqual(self.resize_calls, 2, "a node below an opted-out node must not be reused either")

    def test_identical_nodes_in_one_graph_each_run(self):
        graph = self._graph(seed=-1)
        second = graph_model.new_node("generate_video", "Gen 2")
        second["id"] = "gen2"
        second["params"] = dict(graph["nodes"][0]["params"])
        graph["nodes"].append(second)
        self._run(graph)
        self.assertEqual(self.gen_calls, 2, "two nodes with the same configuration are two generations")

    def test_other_workflow_does_not_reuse_a_failed_run(self):
        graph = self._graph(seed=-1)
        self.resize_fail_once = True
        with self.assertRaises(RuntimeError):
            self._run(graph)
        other = self._graph(seed=-1)
        other["name"] = "A different workflow"
        self._run(other)
        self.assertEqual(self.gen_calls, 2)

    def test_environment_switch_disables_everything(self):
        os.environ["WANFLOW_NO_CACHE"] = "1"
        graph = self._graph(seed=7)
        self._run(graph)
        self._run(graph)
        self.assertEqual(self.gen_calls, 2)
        self.assertFalse((self.out / run_cache.CACHE_DIR_NAME).exists())


class CompareNodeTests(unittest.TestCase):
    """The Compare A/B node, driven through run_graph with stubbed generations."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.out = self.tmp / "out"
        os.environ.pop("WANFLOW_NO_CACHE", None)
        self.calls = 0
        self.compare_args = None

    def tearDown(self):
        self._tmp.cleanup()

    def _fake_generation(self, plugin, api, state, node, *_args, **_kwargs):
        self.calls += 1
        path = self.tmp / f"{node['id']}-{self.calls}.mp4"
        path.write_bytes(b"mp4")
        return str(path)

    def _fake_compare(self, a, b, output, layout="side_by_side", labels=True, cancel_check=None):
        self.compare_args = (Path(a).name, Path(b).name, layout, labels)
        target = Path(output).with_suffix(".mp4")
        target.write_bytes(b"cmp")
        return str(target)

    def _fake_info(self, path):
        return {"width": 1024, "height": 576, "fps": 24.0, "duration": 5.0, "size": 2097152, "has_audio": False}

    def _graph(self, layout="side_by_side", labels=True, seed_b=2):
        graph = graph_model.new_graph("compare")
        nodes = []
        for node_id, seed in (("a", 1), ("b", seed_b)):
            node = graph_model.new_node("generate_video", f"Variant {node_id.upper()}")
            node["id"] = node_id
            node["params"] = {"model_type": "model_a", "seed": seed}
            nodes.append(node)
        compare = graph_model.new_node("compare_ab", "Compare")
        compare["id"] = "cmp"
        compare["params"] = {"layout": layout, "labels": labels}
        graph["nodes"] = nodes + [compare]
        graph["edges"] = [
            {"id": "ea", "source": {"node": "a", "port": "output"}, "target": {"node": "cmp", "port": "a"}, "type": "VIDEO"},
            {"id": "eb", "source": {"node": "b", "port": "output"}, "target": {"node": "cmp", "port": "b"}, "type": "VIDEO"},
        ]
        graph["settings"] = {"aspect_ratio": "source"}
        return graph

    def _run(self, graph):
        results = {}

        def node_callback(node_id, state, result):
            if state == "done":
                results[node_id] = result

        with mock.patch.object(graph_runner, "_submit_generation", self._fake_generation),                 mock.patch.object(graph_runner.media_ops, "compare", self._fake_compare),                 mock.patch.object(graph_runner.media_ops, "video_stream_info", self._fake_info):
            graph_runner.run_graph(_StubPlugin(), None, {}, graph, [], output_root=self.out, node_callback=node_callback)
        return results

    def test_node_has_two_media_inputs_and_two_outputs(self):
        ports = graph_model.node_ports(graph_model.new_node("compare_ab"))
        self.assertEqual({name for name, port in ports.items() if port["direction"] == "in"}, {"a", "b"})
        self.assertEqual({name for name, port in ports.items() if port["direction"] == "out"}, {"output", "report"})
        self.assertEqual(graph_model.validate_graph(self._graph()), [])

    def test_compare_runs_with_layout_and_reports_both_sides(self):
        results = self._run(self._graph(layout="stacked", labels=False))
        self.assertEqual(self.compare_args[2:], ("stacked", False))
        report = results["cmp"]["report"]
        self.assertIn("A: Variant A", report)
        self.assertIn("B: Variant B", report)
        self.assertIn("1024x576", report)
        self.assertIn("24.00 fps", report)
        self.assertEqual(report.count("generated in"), 2)
        # both variants use the same model: the first one also paid for loading it, so no speed verdict
        self.assertEqual(report.count("includes model loading"), 1)
        self.assertIn("Times are not comparable", report)
        self.assertNotIn("was faster by", report)
        self.assertTrue(Path(results["cmp"]["output"]).is_file())

    def test_reused_side_is_reported_as_reused(self):
        graph = self._graph(seed_b=5)
        self._run(graph)
        results = self._run(graph)
        self.assertEqual(self.calls, 2, "fixed seeds are reused, only the first run generates")
        report = results["cmp"]["report"]
        self.assertEqual(report.count("reused earlier result"), 2)
        self.assertNotIn("was faster by", report)

    def test_missing_input_is_an_error(self):
        graph = self._graph()
        graph["edges"] = graph["edges"][:1]
        with self.assertRaises(Exception):
            self._run(graph)


class CompareReportTests(unittest.TestCase):
    def _report(self, **kwargs):
        with mock.patch.object(graph_runner.media_ops, "video_stream_info", lambda path: {"width": 64, "height": 64, "fps": 0.0, "duration": 0.0, "size": 1048576, "has_audio": False}):
            return graph_runner.compare_report("a.png", "b.png", "A node", "B node", **kwargs)

    def test_fair_timings_give_a_speed_verdict(self):
        report = self._report(a_seconds=10.0, b_seconds=20.0, a_reused=False, b_reused=False)
        self.assertIn("A was faster by 2.00x", report)

    def test_loading_time_in_one_side_suppresses_the_verdict(self):
        report = self._report(a_seconds=50.0, b_seconds=10.0, a_reused=False, b_reused=False, a_loaded=True)
        self.assertIn("A: A node | 64x64 | 1.0 MB | generated in 50.0 s (includes model loading)", report)
        self.assertIn("Times are not comparable: A also includes loading the model", report)
        self.assertNotIn("was faster by", report)


class NodeKeyIgnoresRunBehaviourTests(unittest.TestCase):
    def _key(self, settings=None, variables=None):
        graph = {"name": "g", "settings": {"aspect_ratio": "source", **(settings or {})}}
        node = {"id": "n", "type": "generate_video", "params": {"seed": 1}}
        return run_cache.node_key(node, graph, variables or {}, [])

    def test_preflight_and_unload_settings_do_not_change_the_key(self):
        base = self._key()
        self.assertEqual(base, self._key({"preflight": "block"}))
        self.assertEqual(base, self._key({"unload_on_model_change": True, "unload_around_heavy_processing": True}))

    def test_preflight_text_in_the_variables_does_not_change_the_key(self):
        self.assertEqual(self._key(variables={}), self._key(variables={"preflight": "[warning] only 1.0 GB of RAM"}))

    def test_settings_and_variables_that_matter_still_change_the_key(self):
        self.assertNotEqual(self._key(), self._key({"aspect_ratio": "16:9"}))
        self.assertNotEqual(self._key(), self._key(variables={"analysis": "a red car"}))


class RunCacheUnitTests(unittest.TestCase):
    def test_seed_detection(self):
        graph = {"settings": {}}
        self.assertTrue(run_cache.seed_is_fixed({"params": {"seed": 0}}, graph))
        self.assertTrue(run_cache.seed_is_fixed({"params": {"settings": {"seed": 12}}}, graph))
        self.assertFalse(run_cache.seed_is_fixed({"params": {"seed": -1}}, graph))
        self.assertFalse(run_cache.seed_is_fixed({"params": {}}, graph))
        self.assertFalse(run_cache.seed_is_fixed({"params": {"seed": "random"}}, graph))

    def test_fingerprint_changes_when_a_file_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "a.txt"
            path.write_text("one")
            before = run_cache.fingerprint_value({"x": str(path)})
            path.write_text("two-longer")
            self.assertNotEqual(before, run_cache.fingerprint_value({"x": str(path)}))


if __name__ == "__main__":
    unittest.main()
