"""Prompt Engineer CPU-only contract tests."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location("test_" + name, ROOT / (name + ".py"))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


P = load("prompt_engineer")
G = load("graph_model")


class PromptEngineerTests(unittest.TestCase):
    def test_typed_ports(self):
        node = G.new_node("prompt_engineer", params={"mode": "both"})
        self.assertEqual(set(G.node_ports(node)), {"idea", "images", "image_prompt", "video_prompt"})
        self.assertEqual(G.node_ports(node)["images"]["type"], "IMAGE[]")
        node["params"]["mode"] = "image"
        self.assertNotIn("video_prompt", G.node_ports(node))
        node["params"]["mode"] = "video"
        self.assertNotIn("image_prompt", G.node_ports(node))

    def test_graph_validation(self):
        node = G.new_node("prompt_engineer", params={"mode": "invalid"})
        graph = G.new_graph()
        graph["nodes"] = [node]
        self.assertTrue(any("requires Image" in error for error in G.validate_graph(graph)))

    def test_reference_only_and_missing_idea(self):
        self.assertIn("initial frame", P.build_instruction("", "video", True))
        with self.assertRaisesRegex(ValueError, "needs an idea"):
            P.build_instruction("", "both", False)

    def test_both_json(self):
        raw = chr(96) * 3 + 'json\n{"image_prompt":"Still","video_prompt":"Motion"}\n' + chr(96) * 3
        self.assertEqual(P.parse_response(raw), {"image_prompt": "Still", "video_prompt": "Motion"})

    def test_label_fallback(self):
        self.assertEqual(P.parse_response("IMAGE PROMPT: Still\nVIDEO PROMPT: Motion"),
                         {"image_prompt": "Still", "video_prompt": "Motion"})

    def test_single_mode_and_invalid_response(self):
        self.assertEqual(P.parse_response("Still", "image"), {"image_prompt": "Still"})
        self.assertEqual(P.parse_response("Move", "video"), {"video_prompt": "Move"})
        with self.assertRaisesRegex(ValueError, "expected JSON"):
            P.parse_response("something else", "both")
        with self.assertRaisesRegex(ValueError, "no video_prompt"):
            P.parse_response('{"image_prompt":"ok","video_prompt":""}', "both")


if __name__ == "__main__":
    unittest.main()
