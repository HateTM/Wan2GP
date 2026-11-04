"""Input nodes accept an explicit file path (WanGP Studio "Use in workflow").

The Studio gallery drops media files into input nodes as params.path; the
runner must prefer that path over the runtime upload slots and fail loudly
when the file is gone.
"""
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

# graph_runner's relative imports need a real parent package with __path__.
_package = types.ModuleType("wanflow_ui_test_pkg")
_package.__path__ = [str(ROOT)]
sys.modules["wanflow_ui_test_pkg"] = _package


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"wanflow_ui_test_pkg.{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"wanflow_ui_test_pkg.{name}"] = module
    spec.loader.exec_module(module)
    return module


graph_model = _load("graph_model")
graph_runner = _load("graph_runner")


class InputPathParamTests(unittest.TestCase):
    def test_input_image_prefers_explicit_path(self):
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory) / "from-gallery.png"
            media.write_bytes(b"\x89PNG\r\n\x1a\n")
            out = Path(directory) / "out"
            out.mkdir()
            graph = graph_model.new_graph("Use in workflow")
            source = graph_model.new_node("input_image", params={"path": str(media)})
            graph["nodes"] = [source]
            outputs, variables = graph_runner.run_graph(
                None, None, {}, graph, output_root=str(out)
            )
            self.assertEqual(outputs, [str(media)])

    def test_input_image_reports_missing_explicit_file(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "out"
            out.mkdir()
            graph = graph_model.new_graph("Use in workflow")
            source = graph_model.new_node("input_image", params={"path": str(Path(directory) / "gone.png")})
            graph["nodes"] = [source]
            with self.assertRaises(ValueError) as ctx:
                graph_runner.run_graph(None, None, {}, graph, output_root=str(out))
            self.assertIn("needs the file", str(ctx.exception))

    def test_input_image_still_binds_runtime_slots_without_path(self):
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory) / "uploaded.png"
            media.write_bytes(b"\x89PNG\r\n\x1a\n")
            out = Path(directory) / "out"
            out.mkdir()
            graph = graph_model.new_graph("Runtime upload")
            source = graph_model.new_node("input_image", params={})
            graph["nodes"] = [source]
            outputs, _ = graph_runner.run_graph(
                None, None, {}, graph, runtime_inputs=[str(media)], output_root=str(out)
            )
            self.assertEqual(outputs, [str(media)])


if __name__ == "__main__":
    unittest.main()
