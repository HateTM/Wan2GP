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


preflight = _load("preflight")
graph_runner = _load("graph_runner")
graph_model = _load("graph_model")

GIB = preflight.GIB
SIZES = {
    "h3.safetensors": 14 * GIB,
    "h3_encoder.safetensors": 24 * GIB,
    "ltx.safetensors": 17 * GIB,
}
MODEL_DEFS = {
    "h3": {"URLs": ["h3.safetensors"], "text_encoder_URLs": ["h3_encoder.safetensors"]},
    "ltx": {"URLs": ["ltx.safetensors"]},
    "ltx_vfx": {"URLs": "ltx"},  # a reference to another model type
    "missing": {"URLs": ["not-downloaded.safetensors"]},
    "encoder_elsewhere": {"URLs": ["ltx.safetensors"], "text_encoder_URLs": ["encoder_in_subfolder_bf16.safetensors"]},
    "alternatives": {"URLs": ["alt_bf16.safetensors", "ltx.safetensors"]},  # one variant is on disk
}


def get_model_def(model_type):
    return MODEL_DEFS.get(model_type)


def locate(name):
    return name if name in SIZES else None


def snapshot(**overrides):
    base = {
        "ram_total": 32 * GIB, "ram_available": 20 * GIB,
        "commit_limit": 64 * GIB, "commit_available": 30 * GIB,
        "vram_total": 12 * GIB, "vram_free": 11 * GIB, "disk_free": 100 * GIB,
    }
    base.update(overrides)
    return base


def graph_of(*models, **settings):
    graph = graph_model.new_graph("preflight")
    nodes = []
    for index, model_type in enumerate(models):
        node = graph_model.new_node("generate_video", f"Gen {index}")
        node["id"] = f"g{index}"
        node["params"] = {"model_type": model_type}
        nodes.append(node)
    graph["nodes"] = nodes
    graph["settings"] = dict(settings)
    return graph


def run_check(graph, snap=None, release=False, fraction=0.4):
    with mock.patch.object(preflight, "_size", lambda name, loc: SIZES.get(name)):
        return preflight.check(graph, get_model_def, locate=locate, snapshot=snap or snapshot(), fraction=fraction, release_models=release)


def codes(issues):
    return [issue["code"] for issue in issues]


class PreflightCheckTests(unittest.TestCase):
    def test_roomy_machine_has_no_warnings(self):
        self.assertEqual(run_check(graph_of("h3")), [])

    def test_low_commit_memory_is_flagged_like_the_real_failure(self):
        # the machine that failed: 7.7 GB of commit left while a 14 GB checkpoint wants about 12.5 GB pinned
        issues = run_check(graph_of("h3"), snapshot(commit_available=7.7 * GIB))
        self.assertEqual(codes(issues), ["commit"])
        message = issues[0]["message"]
        self.assertIn("7.7 GB", message)
        self.assertIn("page file", message)
        self.assertIn("perc_reserved_mem_max", message)

    def test_pinned_estimate_is_capped_by_the_reserved_ram_share(self):
        self.assertEqual(preflight.estimate_pinned_ram(14 * GIB, 32 * GIB, 0.4), int(32 * GIB * 0.4))
        self.assertEqual(preflight.estimate_pinned_ram(5 * GIB, 32 * GIB, 0.4), 5 * GIB)
        self.assertEqual(preflight.estimate_pinned_ram(14 * GIB, None, 0.4), 14 * GIB)

    def test_lowering_the_reserved_share_removes_the_warning(self):
        low_commit = snapshot(commit_available=14 * GIB)
        self.assertEqual(codes(run_check(graph_of("h3"), low_commit, fraction=0.4)), ["commit"])
        self.assertEqual(run_check(graph_of("h3"), low_commit, fraction=0.2), [])

    def test_low_physical_ram_is_flagged(self):
        issues = run_check(graph_of("h3"), snapshot(ram_available=2 * GIB))
        self.assertIn("ram", codes(issues))

    def test_several_models_stay_resident_unless_unloading_is_on(self):
        graph = graph_of("h3", "ltx")
        self.assertIn("resident", codes(run_check(graph, release=False)))
        self.assertNotIn("resident", codes(run_check(graph, release=True)))

    def test_unloading_uses_the_largest_model_not_the_sum_for_the_commit_check(self):
        snap = snapshot(commit_available=17 * GIB)  # enough for one 12.8 GB share + margin, not for two
        graph = graph_of("h3", "ltx")
        self.assertIn("commit", codes(run_check(graph, snap, release=False)))
        self.assertNotIn("commit", codes(run_check(graph, snap, release=True)))

    def test_model_reference_is_followed(self):
        files = preflight.model_files("ltx_vfx", get_model_def)
        self.assertEqual(files["main"], ["ltx.safetensors"])

    def test_missing_files_are_announced_as_a_download(self):
        issues = run_check(graph_of("missing"))
        self.assertEqual(codes(issues), ["download"])
        self.assertEqual(issues[0]["level"], "info")
        self.assertIn("not-downloaded.safetensors", issues[0]["message"])

    def test_unlocatable_text_encoder_is_not_reported_as_a_download(self):
        self.assertEqual(run_check(graph_of("encoder_elsewhere")), [])

    def test_alternative_weights_count_as_present_when_one_is_on_disk(self):
        self.assertEqual(run_check(graph_of("alternatives")), [])

    def test_low_vram_and_disk_are_flagged(self):
        issues = run_check(graph_of("ltx"), snapshot(vram_free=1 * GIB, disk_free=2 * GIB))
        self.assertTrue({"vram", "disk"} <= set(codes(issues)))

    def test_unknown_values_never_raise_or_warn(self):
        unknown = {key: None for key in snapshot()}
        self.assertEqual(run_check(graph_of("h3"), unknown), [])

    def test_a_broken_model_lookup_does_not_raise(self):
        def broken(model_type):
            raise RuntimeError("boom")
        with mock.patch.object(preflight, "_size", lambda name, loc: None):
            self.assertEqual(preflight.check(graph_of("h3"), broken, locate=locate, snapshot=snapshot()), [])

    def test_disabled_nodes_are_ignored(self):
        graph = graph_of("h3")
        graph["nodes"][0]["enabled"] = False
        self.assertEqual(run_check(graph, snapshot(commit_available=1 * GIB)), [])


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


class PreflightRunTests(unittest.TestCase):
    WARNING = [{"level": "warning", "code": "commit", "message": "only 7.7 GB of commit left"}]

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        os.environ["WANFLOW_NO_CACHE"] = "1"
        self.messages: list[str] = []
        self.generated = 0

    def tearDown(self):
        os.environ.pop("WANFLOW_NO_CACHE", None)
        self._tmp.cleanup()

    def _generation(self, *_args, **_kwargs):
        self.generated += 1
        path = self.tmp / f"gen-{self.generated}.mp4"
        path.write_bytes(b"x")
        return str(path)

    def _run(self, settings=None, check=None):
        graph = graph_model.new_graph("pf")
        node = graph_model.new_node("generate_video", "Gen")
        node["id"] = "g"
        node["params"] = {"model_type": "model_a", "seed": 1}
        graph["nodes"] = [node]
        graph["settings"] = {"aspect_ratio": "source", **(settings or {})}
        with mock.patch.object(graph_runner, "_submit_generation", self._generation), \
                mock.patch.object(graph_runner.preflight, "check", check or (lambda *a, **k: list(self.WARNING))):
            return graph_runner.run_graph(_StubPlugin(), None, {}, graph, [], output_root=self.tmp / "out", callback=lambda text, value: self.messages.append(text))

    def test_warning_is_shown_and_the_run_continues(self):
        _, variables = self._run()
        self.assertTrue(any(message.startswith("Preflight warning: only 7.7 GB") for message in self.messages))
        self.assertIn("only 7.7 GB", variables["preflight"])
        self.assertEqual(self.generated, 1)

    def test_block_mode_stops_before_anything_runs(self):
        with self.assertRaises(ValueError) as caught:
            self._run({"preflight": "block"})
        self.assertIn("only 7.7 GB", str(caught.exception))
        self.assertEqual(self.generated, 0)

    def test_block_mode_lets_info_findings_through(self):
        info_only = lambda *a, **k: [{"level": "info", "code": "download", "message": "will download"}]
        self._run({"preflight": "block"}, check=info_only)
        self.assertEqual(self.generated, 1)

    def test_off_skips_the_check(self):
        called = []
        self._run({"preflight": "off"}, check=lambda *a, **k: called.append(1) or [])
        self.assertEqual(called, [])

    def test_a_failing_check_never_stops_the_run(self):
        def broken(*args, **kwargs):
            raise RuntimeError("boom")
        self._run(check=broken)
        self.assertEqual(self.generated, 1)


if __name__ == "__main__":
    unittest.main()
