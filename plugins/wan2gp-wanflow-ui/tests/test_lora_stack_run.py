from __future__ import annotations

import importlib.util
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


class _StubPlugin:
    def list_model_defs(self):
        return []

    def get_model_def(self, model_type):
        return None

    def get_default_settings(self, model_type):
        return {}


class _StubAPI:
    def submit_task(self, settings, callbacks=None):  # pragma: no cover - not reached
        raise AssertionError("no generation node in this graph")


class TestLoraStackRun(unittest.TestCase):
    """Regression: the lora_stack node used to shadow run_graph's `values`
    accumulator with its local `values` list, so `values[node_id] = result`
    raised "list indices must be integers or slices, not str" and killed any
    workflow containing a LoRA Stack node."""

    def test_lora_stack_node_runs(self):
        graph = {
            "schema": "wan2gp-wanflow-ui",
            "version": 1,
            "id": "regression",
            "name": "lora regression",
            "settings": {},
            "nodes": [
                {"id": "lora", "type": "lora_stack", "title": "LoRA",
                 "params": {"model_type": "ltx2_25_22B_redgraft_nsfw",
                            "base_model_type": "ltx2_25_22B",
                            "activated_loras": ["demo.safetensors"],
                            "loras_multipliers": "0.7"},
                 "ui": {}, "enabled": True},
            ],
            "edges": [],
            "groups": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            outputs, _variables = graph_runner.run_graph(
                _StubPlugin(), _StubAPI(), {}, graph,
                output_root=tmp,
            )
        self.assertEqual(outputs, [])


if __name__ == "__main__":
    unittest.main()
