from __future__ import annotations

import importlib.util
import json
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


graph_store = _load("graph_store")


class GraphStoreResolveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = graph_store.GraphStore(self.tmp.name)
        pretty = Path(self.tmp.name) / "LTX25-I2VA-T2VA-Qwen3.5.json"
        pretty.write_text(json.dumps({"name": "LTX25 I2VA", "nodes": [], "edges": []}), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_by_pretty_stem_finds_shipped_file(self):
        graph = self.store.load("LTX25-I2VA-T2VA-Qwen3.5")
        self.assertEqual(graph["name"], "LTX25 I2VA")

    def test_load_by_slugified_name_finds_same_file(self):
        graph = self.store.load("ltx25-i2va-t2va-qwen3-5")
        self.assertEqual(graph["name"], "LTX25 I2VA")

    def test_missing_workflow_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.store.load("does-not-exist")

    def test_delete_resolves_pretty_name(self):
        self.store.delete("LTX25-I2VA-T2VA-Qwen3.5")
        self.assertFalse((Path(self.tmp.name) / "LTX25-I2VA-T2VA-Qwen3.5.json").is_file())


if __name__ == "__main__":
    unittest.main()
