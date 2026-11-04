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

from shared.utils.setting_names import settings_error  # noqa: E402


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


class _StubAPI:
    """Records every submitted prompt; returns a distinct media file per task."""

    def __init__(self, paths):
        self._paths = list(paths)
        self.submitted_prompts: list[str] = []

    def submit_task(self, settings, callbacks=None):
        self.submitted_prompts.append(str(settings.get("prompt") or ""))
        path = self._paths[len(self.submitted_prompts) - 1] if len(self.submitted_prompts) <= len(self._paths) else self._paths[-1]
        return _Job(path)


class _Job:
    def __init__(self, path: str):
        self._path = path
        self.done = True

    def result(self):
        return _Result(self._path)

    def cancel(self):
        pass


class _StubPlugin:
    def get_model_def(self, model_type):
        return {"base_model_type": "test", "vae_block_size": 16}

    def get_default_settings(self, model_type):
        return {}

    def get_model_family(self, model_type, for_ui=True):
        return "test"

    def get_resolution_choices(self, resolution, model_def):
        return [("720p", "720x1280")], None


class MultiPromptSplitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.paths = [str(Path(self.tmp.name) / f"out_{i}.png") for i in range(5)]
        for path in self.paths:
            Path(path).write_bytes(b"png")

    def tearDown(self):
        self.tmp.cleanup()

    def _submit_with_stub(self, settings, stub):
        node = {
            "id": "n1",
            "type": "generate_image",
            "title": "Generation",
            "params": {"model_type": "test_model", "settings": settings},
            "enabled": True,
        }
        return graph_runner._submit_generation(
            _StubPlugin(),
            stub,
            {},
            node,
            inputs={},
            variables={},
            workflow_settings={},
            output_root=ROOT / "tests" / "tmp_out",
            callback=None,
            cancel_check=None,
        )

    def test_g_mode_prompt_splits_into_separate_tasks(self):
        stub = _StubAPI(self.paths)
        result = self._submit_with_stub({
            "prompt": "pose one\npose two\npose three",
            "multi_prompts_gen_type": "G",
        }, stub)
        self.assertEqual(len(stub.submitted_prompts), 3)
        self.assertEqual(stub.submitted_prompts, ["pose one", "pose two", "pose three"])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)

    def test_single_line_prompt_submits_one_task(self):
        stub = _StubAPI(self.paths)
        result = self._submit_with_stub({
            "prompt": "one pose only",
            "multi_prompts_gen_type": "G",
        }, stub)
        self.assertEqual(len(stub.submitted_prompts), 1)
        self.assertEqual(result, self.paths[0])

    def test_pw_mode_stays_one_task(self):
        stub = _StubAPI(self.paths)
        result = self._submit_with_stub({
            "prompt": "window one\n\nwindow two",
            "multi_prompts_gen_type": "PW",
        }, stub)
        self.assertEqual(len(stub.submitted_prompts), 1)
        self.assertEqual(result, self.paths[0])

    def test_settings_pass_settings_gate(self):
        settings = {
            "prompt": "pose one\npose two",
            "multi_prompts_gen_type": "G",
            "repeat_generation": 1,
        }
        self.assertEqual(settings_error(settings), "")


if __name__ == "__main__":
    unittest.main()
