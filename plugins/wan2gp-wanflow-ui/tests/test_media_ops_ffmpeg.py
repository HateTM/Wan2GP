from __future__ import annotations

import importlib.util
import subprocess
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


media_ops = _load("media_ops")


class FfmpegOptionTests(unittest.TestCase):
    def test_source_does_not_use_the_removed_vsync_option(self):
        # FFmpeg 9 removed -vsync (replaced by -fps_mode, available since 5.1).
        self.assertNotIn('"-vsync"', (ROOT / "media_ops.py").read_text(encoding="utf-8"))

    def test_real_ffmpeg_fps_and_frame_extraction(self):
        ffmpeg = media_ops.resolve_media_binary("ffmpeg")
        if not ffmpeg:
            self.skipTest("Wan2GP FFmpeg binary not available")
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.mp4"
            subprocess.run([ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=10", "-t", "1", "-pix_fmt", "yuv420p", str(source)], check=True)
            converted = media_ops.fps(str(source), 24.0, Path(folder) / "fps.mp4")
            self.assertTrue(Path(converted).is_file() and Path(converted).stat().st_size > 0)
            frame = media_ops.extract_frame(str(source), 3, Path(folder) / "frame.png")
            self.assertTrue(Path(frame).is_file() and Path(frame).stat().st_size > 0)
            second = Path(folder) / "second.png"
            subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(source), "-frames:v", "1", str(second)], check=True)
            sequence = media_ops.image_sequence([frame, str(second)], 8.0, Path(folder) / "sequence.mp4")
            self.assertTrue(Path(sequence).is_file() and Path(sequence).stat().st_size > 0)


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.ffmpeg = media_ops.resolve_media_binary("ffmpeg")
        if not self.ffmpeg:
            self.skipTest("Wan2GP FFmpeg binary not available")
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _make(self, name: str, size: str, video: bool = False, rate: int = 10) -> str:
        path = self.dir / name
        command = [self.ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=size={size}:rate={rate}"]
        command += ["-t", "1", "-pix_fmt", "yuv420p"] if video else ["-frames:v", "1"]
        subprocess.run(command + [str(path)], check=True)
        return str(path)

    def test_images_side_by_side_scales_b_to_the_height_of_a(self):
        a, b = self._make("a.png", "64x32"), self._make("b.png", "32x32")
        result = media_ops.compare(a, b, self.dir / "out", "side_by_side", True)
        info = media_ops.video_stream_info(result)
        self.assertTrue(result.endswith(".png"))
        self.assertEqual((info["width"], info["height"]), (64 + 32, 32))

    def test_images_stacked_scales_b_to_the_width_of_a(self):
        a, b = self._make("a.png", "64x32"), self._make("b.png", "32x32")
        result = media_ops.compare(a, b, self.dir / "out", "stacked", False)
        info = media_ops.video_stream_info(result)
        self.assertEqual((info["width"], info["height"]), (64, 32 + 64))

    def test_videos_are_cut_to_the_shorter_one_at_the_frame_rate_of_a(self):
        a = self._make("a.mp4", "64x64", video=True, rate=10)
        b = self._make("b.mp4", "128x64", video=True, rate=25)
        result = media_ops.compare(a, b, self.dir / "out", "side_by_side", True)
        info = media_ops.video_stream_info(result)
        self.assertTrue(result.endswith(".mp4"))
        self.assertEqual(info["height"], 64)
        self.assertAlmostEqual(info["fps"], 10.0, delta=0.1)
        self.assertLessEqual(info["duration"], 1.2)

    def test_mixed_kinds_are_rejected(self):
        with self.assertRaises(ValueError):
            media_ops.compare(self._make("a.png", "32x32"), self._make("b.mp4", "32x32", video=True), self.dir / "out")


if __name__ == "__main__":
    unittest.main()
