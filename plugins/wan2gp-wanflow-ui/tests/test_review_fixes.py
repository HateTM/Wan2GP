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


runtime_engine = _load("runtime_engine")
graph_model = _load("graph_model")


class SubstituteVariablesTests(unittest.TestCase):
    def test_dollar_amounts_stay_literal(self):
        text = "Price is $5 today, 100 $ for two"
        result = runtime_engine.substitute_variables(text, {})
        self.assertEqual(result, text)

    def test_defined_variable_is_substituted_and_unknown_stays_literal(self):
        self.assertEqual(runtime_engine.substitute_variables("hello $name", {"name": "world"}), "hello world")
        self.assertEqual(runtime_engine.substitute_variables("stay $unknown", {}), "stay $unknown")


class MigrateV1Tests(unittest.TestCase):
    def test_postprocess_stage_targets_existing_port(self):
        payload = {
            "schema": graph_model.LEGACY_SCHEMA,
            "name": "legacy",
            "stages": [
                {"id": "s1", "stage_type": "generation", "settings": {"model_type": "m1", "image_mode": 0}},
                {"id": "s2", "stage_type": "spatial", "processor_settings": {}},
                {"id": "s3", "stage_type": "ai_analysis", "processor_settings": {}},
            ],
        }
        graph = graph_model.migrate_v1_workflow(payload)
        errors = graph_model.validate_graph(graph, None)
        self.assertEqual(errors, [])
        by_node = {}
        for edge in graph["edges"]:
            by_node.setdefault(edge["target"]["node"], []).append(edge["target"]["port"])
        self.assertIn("media", by_node.get("s2", []))
        self.assertIn("images", by_node.get("s3", []))


if __name__ == "__main__":
    unittest.main()
