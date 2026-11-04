from __future__ import annotations

import importlib.util
import sys
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

from shared.utils.setting_names import settings_error  # noqa: E402


class _Job:
    done = True
    cancelled = False
    success = False
    errors = ["(test stops before generation)"]

    def result(self):
        return self

    def cancel(self):
        pass


class _StubAPI:
    def __init__(self):
        self.captured = None

    def submit_task(self, settings, callbacks=None):
        self.captured = settings
        return _Job()


class _StubPlugin:
    def get_model_def(self, model_type):
        return {"base_model_type": "minimax_h3", "vae_block_size": 16}

    def get_default_settings(self, model_type):
        return {}

    def get_model_family(self, model_type, for_ui=True):
        return "minimax_h3"

    def get_resolution_choices(self, resolution, model_def):
        return [("720p", "720x1280")], None


def _submit(node_params: dict, inputs: dict | None = None) -> dict:
    node = {
        "id": "n1",
        "type": "generate_video",
        "title": "Generation",
        "params": node_params,
        "enabled": True,
    }
    api = _StubAPI()
    try:
        graph_runner._submit_generation(
            _StubPlugin(),
            api,
            {},
            node,
            inputs=inputs or {},
            variables={},
            workflow_settings={},
            output_root=ROOT / "tests" / "tmp_out",
            callback=None,
            cancel_check=None,
        )
    except RuntimeError as exc:
        if "(test stops before generation)" not in str(exc):
            raise
    assert api.captured is not None, "submit_task was never reached"
    return api.captured


class GraphRunnerSettingsTests(unittest.TestCase):
    def test_inline_steps_value_maps_to_accepted_setting(self):
        settings = _submit({
            "model_type": "minimax_h3_10eros_max_b5_fl2va",
            "steps": 8,
            "num_inference_steps": 8,
        })
        self.assertNotIn("steps", settings)
        self.assertEqual(settings.get("num_inference_steps"), 8)
        self.assertEqual(settings_error(settings), "")

    def test_sampling_config_steps_value_maps_to_accepted_setting(self):
        settings = _submit(
            {"model_type": "minimax_h3_10eros_max_b5_fl2va"},
            inputs={"sampling_config": [{"steps": 8, "num_inference_steps": 8}]},
        )
        self.assertNotIn("steps", settings)
        self.assertEqual(settings.get("num_inference_steps"), 8)
        self.assertEqual(settings_error(settings), "")

    def test_model_default_steps_uses_model_default(self):
        settings = _submit({"model_type": "minimax_h3_10eros_max_b5_fl2va"})
        self.assertNotIn("steps", settings)
        self.assertNotIn("num_inference_steps", settings)
        self.assertEqual(settings_error(settings), "")


if __name__ == "__main__":
    unittest.main()
