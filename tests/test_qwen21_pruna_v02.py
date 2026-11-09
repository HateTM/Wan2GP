"""Regression tests for Qwen Image 2.1 accelerator profiles (stdlib only)."""
import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "models" / "qwen21" / "pipeline.py"
HANDLER = ROOT / "models" / "qwen21" / "qwen21_handler.py"
PROFILE_DIR = ROOT / "profiles" / "qwen21"
EDIT_DIR = ROOT / "shared" / "deepy" / "settings" / "edit_image"
GEN_DIR = ROOT / "shared" / "deepy" / "settings" / "gen_image"


def assignment_value(source, name):
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"Assignment {name} not found")


class Qwen21PrunaV02Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = PIPELINE.read_text(encoding="utf-8")
        cls.handler = HANDLER.read_text(encoding="utf-8")

    def test_v02_sigma_schedule_matches_official_unshifted_values(self):
        schedule = assignment_value(self.pipeline, "PRUNA_V02_SIGMAS")
        self.assertEqual(
            schedule,
            {6: (1.0, 0.925, 0.85, 0.625, 0.375, 0.125)},
        )

    def test_v02_solver_is_six_step_and_uses_dynamic_shift(self):
        self.assertIn('pruna_v02 = sample_solver == "pruna_v02"', self.pipeline)
        self.assertIn("if pruna_v02 and sampling_steps not in PRUNA_V02_SIGMAS:", self.pipeline)
        self.assertIn('{"use_dynamic_shifting": True, "shift_terminal": None} if pruna_v02', self.pipeline)
        self.assertIn("PRUNA_V02_SIGMAS[sampling_steps] if pruna_v02", self.pipeline)

    def test_v02_solver_is_exposed_in_model_settings(self):
        self.assertIn('("Pruna v0.2", "pruna_v02")', self.handler)

    def test_profile_jsons_match_their_adapters(self):
        cases = (
            ("Pruna v0.2 6 Steps.json", "p_q_image_2.1_6_steps_v0.2.safetensors"),
            ("Pruna v0.2 6 Steps Upsampled.json", "p_q_image_2.1_6_steps_upsampled_v0.2.safetensors"),
        )
        for profile_name, adapter_name in cases:
            with self.subTest(profile=profile_name):
                data = json.loads((PROFILE_DIR / profile_name).read_text(encoding="utf-8"))
                self.assertEqual(data["sample_solver"], "pruna_v02")
                self.assertEqual(data["num_inference_steps"], 6)
                self.assertEqual(data["guidance_scale"], 1)
                self.assertEqual(data["loras_multipliers"], "1")
                self.assertIn(adapter_name, data["activated_loras"][0])

    def test_deepy_generation_and_editing_recipes_exist(self):
        variants = (
            ("Qwen Image 2.1 Pruna v0.2 6 Steps.json", "p_q_image_2.1_6_steps_v0.2.safetensors"),
            ("Qwen Image 2.1 Pruna v0.2 6 Steps Upsampled.json", "p_q_image_2.1_6_steps_upsampled_v0.2.safetensors"),
        )
        for directory in (EDIT_DIR, GEN_DIR):
            for recipe_name, adapter_name in variants:
                with self.subTest(directory=directory.name, recipe=recipe_name):
                    data = json.loads((directory / recipe_name).read_text(encoding="utf-8"))
                    self.assertEqual(data["model_type"], "qwen_image_21_7B")
                    self.assertEqual(data["sample_solver"], "pruna_v02")
                    self.assertEqual(data["num_inference_steps"], 6)
                    self.assertEqual(data["guidance_scale"], 1.0)
                    self.assertEqual(data["prompt_enhancer"], "")
                    self.assertIn(adapter_name, data["activated_loras"][0])

    def test_existing_accelerator_profiles_are_preserved(self):
        existing = (
            ("Pruna v0.1 5 Steps.json", "pruna", 5),
            ("Pruna v0.1 8 Steps.json", "pruna", 8),
            ("Viggle Turbo 4 Steps.json", "viggle_v02", 4),
            ("Viggle Turbo v0.2 5 Steps.json", "viggle_v02", 5),
            ("Viggle Turbo v0.2.1 6 Steps.json", "viggle_v02", 6),
            ("Viggle Turbo v0.3 6 Steps.json", "viggle_v02", 6),
        )
        for profile_name, solver, steps in existing:
            with self.subTest(profile=profile_name):
                data = json.loads((PROFILE_DIR / profile_name).read_text(encoding="utf-8"))
                self.assertEqual(data["sample_solver"], solver)
                self.assertEqual(data["num_inference_steps"], steps)


if __name__ == "__main__":
    unittest.main()
