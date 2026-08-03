from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.parser import parse_docx_exam
from backend.app.services.parser.preview_renderer import render_exam_preview


class DocxParserGoldenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sample_path = PROJECT_ROOT / "data" / "samples" / "de-mau-azota.docx"
        expected_path = PROJECT_ROOT / "data" / "samples" / "de-mau-azota.expected.json"
        cls.expected = json.loads(expected_path.read_text(encoding="utf-8"))

    def test_parse_sample_counts_answers_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_docx_exam(self.sample_path, assets_dir=Path(tmp) / "assets")

        self.assertIn(self.expected["title_contains"], parsed["title"])
        sections = {section["type"]: section for section in parsed["sections"]}

        for section_type, section_expected in self.expected["sections"].items():
            with self.subTest(section=section_type):
                self.assertEqual(section_expected["count"], len(sections[section_type]["questions"]))

        single_choice_answers = {
            str(question["number"]): question["correct_answer"]
            for question in sections["single_choice"]["questions"]
        }
        self.assertEqual(self.expected["sections"]["single_choice"]["answer_key"], single_choice_answers)

        true_false_answers = {
            str(question["number"]): question["correct_answer"]
            for question in sections["true_false"]["questions"]
        }
        self.assertEqual(self.expected["sections"]["true_false"]["answer_key"], true_false_answers)

        short_answers = {
            str(question["number"]): question["correct_answer"]
            for question in sections["short_answer"]["questions"]
        }
        self.assertEqual(self.expected["sections"]["short_answer"]["answer_key"], short_answers)

        self.assertEqual(self.expected["expected_assets"]["wmf_count"], len(parsed["assets"]))
        self.assertTrue(all(asset["extension"] == ".wmf" for asset in parsed["assets"]))
        self.assertTrue(all(asset["status"] == "placeholder" for asset in parsed["assets"]))
        self.assertTrue(any(warning["code"] == "UNCONVERTED_VECTOR_IMAGE" for warning in parsed["warnings"]))

    def test_inline_images_keep_word_display_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_docx_exam(self.sample_path, assets_dir=Path(tmp) / "assets")

        image_blocks = _image_blocks(parsed)
        first = image_blocks[0]
        second = image_blocks[1]

        self.assertEqual("img_0001", first["asset_id"])
        self.assertEqual({"cx": 352425, "cy": 200025}, first["extent_emu"])
        self.assertAlmostEqual(37, first["display_width_px"], delta=0.2)
        self.assertAlmostEqual(21, first["display_height_px"], delta=0.2)

        self.assertEqual("img_0002", second["asset_id"])
        self.assertEqual({"cx": 1447800, "cy": 390525}, second["extent_emu"])
        self.assertAlmostEqual(152, second["display_width_px"], delta=0.2)
        self.assertAlmostEqual(41, second["display_height_px"], delta=0.2)

    def test_question_shapes_are_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_docx_exam(self.sample_path, assets_dir=Path(tmp) / "assets")

        sections = {section["type"]: section for section in parsed["sections"]}
        for question in sections["single_choice"]["questions"]:
            with self.subTest(section="single_choice", question=question["number"]):
                self.assertEqual(["A", "B", "C", "D"], list(question["options"]))
                for label in ("A", "B", "C", "D"):
                    self.assertTrue(question["options"][label])
                self.assertTrue(question["prompt_blocks"])

        for question in sections["true_false"]["questions"]:
            with self.subTest(section="true_false", question=question["number"]):
                self.assertEqual(["a", "b", "c", "d"], list(question["statements"]))
                for label in ("a", "b", "c", "d"):
                    self.assertTrue(question["statements"][label])
                self.assertTrue(question["prompt_blocks"])

        for question in sections["short_answer"]["questions"]:
            with self.subTest(section="short_answer", question=question["number"]):
                self.assertTrue(question["prompt_blocks"])

    def test_preview_html_renders_structure_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            parsed = parse_docx_exam(self.sample_path, assets_dir=tmp_path / "assets")
            preview_path = render_exam_preview(parsed, tmp_path / "preview.html")
            html = preview_path.read_text(encoding="utf-8")

        self.assertIn("PHẦN I", html)
        self.assertIn("PHẦN II", html)
        self.assertIn("PHẦN III", html)
        self.assertIn("UNCONVERTED_VECTOR_IMAGE", html)
        self.assertIn("<img", html)
        self.assertIn(".placeholder.svg", html)
        self.assertNotIn("file:///", html)


def _image_blocks(parsed: dict) -> list[dict]:
    blocks: list[dict] = []
    for section in parsed["sections"]:
        for question in section["questions"]:
            blocks.extend(block for block in question.get("prompt_blocks", []) if block.get("type") == "image")
            for key in ("options", "statements"):
                for nested in question.get(key, {}).values():
                    blocks.extend(block for block in nested if block.get("type") == "image")
    return blocks


if __name__ == "__main__":
    unittest.main()
