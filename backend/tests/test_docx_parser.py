from __future__ import annotations

import json
import sys
import tempfile
import unittest
from collections import Counter
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

        extensions = Counter(asset["extension"] for asset in parsed["assets"])
        self.assertEqual(self.expected["expected_assets"]["total_count"], len(parsed["assets"]))
        self.assertEqual(self.expected["expected_assets"]["wmf_count"], extensions[".wmf"])
        self.assertEqual(self.expected["expected_assets"]["png_count"], extensions[".png"])
        self.assertTrue(
            all(asset["status"] == "placeholder" for asset in parsed["assets"] if asset["extension"] == ".wmf")
        )
        self.assertTrue(
            all(asset["status"] == "ready" for asset in parsed["assets"] if asset["extension"] == ".png")
        )
        self.assertTrue(any(warning["code"] == "UNCONVERTED_VECTOR_IMAGE" for warning in parsed["warnings"]))

    def test_pasted_question_images_are_block_illustrations_before_answers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_docx_exam(self.sample_path, assets_dir=Path(tmp) / "assets")

        sections = {section["type"]: section for section in parsed["sections"]}
        expected_questions = (("single_choice", 1), ("single_choice", 3), ("short_answer", 3))

        for section_type, number in expected_questions:
            with self.subTest(section=section_type, question=number):
                question = next(item for item in sections[section_type]["questions"] if item["number"] == number)
                illustration = question["prompt_blocks"][-1]
                self.assertEqual("image", illustration["type"])
                self.assertEqual(".png", illustration["extension"])
                self.assertEqual("ready", illustration["status"])
                self.assertEqual("block", illustration["display_mode"])
                self.assertTrue(question["prompt_markup"].endswith(f"[img:${illustration['asset_id']}$]"))

        self.assertEqual(4, len(sections["single_choice"]["questions"][0]["options"]))
        self.assertEqual(4, len(sections["single_choice"]["questions"][2]["options"]))

        all_illustrations = [
            block
            for block in _image_blocks(parsed)
            if block.get("display_mode") == "block"
        ]
        self.assertEqual(3, len(all_illustrations))

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

    def test_markup_tokens_and_asset_map_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_docx_exam(self.sample_path, assets_dir=Path(tmp) / "assets")

        first_question = parsed["sections"][0]["questions"][0]
        self.assertIn("[img:$img_0001$]", first_question["prompt_markup"])
        self.assertIn("[img:$img_0002$]", first_question["prompt_markup"])
        option_a_image = next(block for block in first_question["options"]["A"] if block.get("type") == "image")
        self.assertEqual(f"[img:${option_a_image['asset_id']}$].", first_question["options_markup"]["A"])

        assets_by_id = parsed["assets_by_id"]
        self.assertIn("img_0001", assets_by_id)
        self.assertEqual({"cx": 352425, "cy": 200025}, assets_by_id["img_0001"]["extent_emu"])
        self.assertAlmostEqual(37, assets_by_id["img_0001"]["display_width_px"], delta=0.2)
        self.assertGreaterEqual(len(assets_by_id["img_0001"]["occurrences"]), 1)
        self.assertEqual({"cx": 352425, "cy": 200025}, assets_by_id["img_0001"]["occurrences"][0]["extent_emu"])

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
        self.assertEqual(3, html.count('class="question-illustration"'))
        self.assertIn(".placeholder.svg", html)
        self.assertNotIn("file:///", html)

    def test_converted_images_are_high_dpi(self) -> None:
        """When convert_images=True (LibreOffice + ImageMagick available),
        render_path should be .png, display sizes unchanged, and actual
        PNG pixel dimensions should exceed display_width_px (3× upscale)."""
        import shutil

        has_lo = bool(shutil.which("soffice") or shutil.which("libreoffice"))
        has_magick = bool(shutil.which("convert") or shutil.which("magick"))
        if not (has_lo and has_magick):
            self.skipTest("LibreOffice and/or ImageMagick not available — skipping high-DPI test")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / "assets"
            parsed = parse_docx_exam(self.sample_path, assets_dir=tmp_path, convert_images=True)

            image_blocks = _image_blocks(parsed)
            self.assertGreater(len(image_blocks), 0, "Expected at least one image block")

            first = image_blocks[0]
            second = image_blocks[1]

            # render_path should be .png
            self.assertTrue(first["render_path"].endswith(".png"), f"Expected .png, got {first['render_path']}")
            self.assertTrue(second["render_path"].endswith(".png"), f"Expected .png, got {second['render_path']}")

            # display sizes should match Word originals
            self.assertAlmostEqual(37, first["display_width_px"], delta=0.2)
            self.assertAlmostEqual(21, first["display_height_px"], delta=0.2)
            self.assertAlmostEqual(152, second["display_width_px"], delta=0.2)
            self.assertAlmostEqual(41, second["display_height_px"], delta=0.2)

            # Actual PNG pixel dimensions should exceed display size (3× upscale)
            try:
                import struct

                def _png_dimensions(png_path: Path) -> tuple[int, int]:
                    """Read width and height from PNG IHDR chunk."""
                    data = png_path.read_bytes()
                    # PNG signature (8 bytes) + IHDR length (4 bytes) + 'IHDR' (4 bytes) + width (4) + height (4)
                    if data[:8] != b"\x89PNG\r\n\x1a\n":
                        raise ValueError("Not a PNG file")
                    w, h = struct.unpack(">II", data[16:24])
                    return w, h

                first_png = Path(first["render_path"])
                if not first_png.is_absolute():
                    first_png = Path.cwd() / first_png
                second_png = Path(second["render_path"])
                if not second_png.is_absolute():
                    second_png = Path.cwd() / second_png

                if first_png.exists():
                    w1, h1 = _png_dimensions(first_png)
                    self.assertGreater(w1, first["display_width_px"],
                                       f"PNG pixel width {w1} should exceed display_width_px {first['display_width_px']}")

                if second_png.exists():
                    w2, h2 = _png_dimensions(second_png)
                    self.assertGreater(w2, second["display_width_px"],
                                       f"PNG pixel width {w2} should exceed display_width_px {second['display_width_px']}")
            except ImportError:
                pass  # struct should always be available, but just in case


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
