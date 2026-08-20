from __future__ import annotations

import base64
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.parser import docx_parser, parse_docx_exam


class OmmlDocxParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sample_path = PROJECT_ROOT / "data" / "samples" / "trig-functions.docx"

    def test_word_math_keeps_fractions_delimiters_and_set_notation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_docx_exam(self.sample_path, assets_dir=Path(tmp) / "assets")

        sections = {section["type"]: section for section in parsed["sections"]}
        question_10 = _question(sections["single_choice"], 10)
        question_11 = _question(sections["single_choice"], 11)
        true_false_1 = _question(sections["true_false"], 1)

        self.assertEqual(
            r"R\setminus \{k\pi  ; k \in  Z)",
            _math_text(question_10["options"]["A"]),
        )
        self.assertEqual(
            r"\mathbb{R}\setminus \left\{\frac{\pi }{2}+k\pi ;k\in \mathbb{Z}\right\}",
            _math_text(question_10["options"]["C"]),
        )
        self.assertEqual(
            r"\left[-1;1\right]\setminus \left\{0\right\}",
            _math_text(question_10["options"]["D"]),
        )
        self.assertEqual(
            [r"y=\cos x", r"x\in \left[-\pi ;\pi \right]."],
            _math_blocks(question_11["prompt_blocks"]),
        )
        self.assertEqual(
            r"D=\mathbb{R}\setminus \left\{\frac{\pi }{2}+k\pi \mid k\in \mathbb{Z}\right\}",
            _math_text(true_false_1["statements"]["a"]),
        )
        self.assertEqual(
            r"f(\frac{\pi }{3})=f(-\frac{\pi }{3})",
            _math_text(true_false_1["statements"]["b"]),
        )
        self.assertEqual(
            r"f\left(-x\right)=-f\left(x\right)",
            _math_text(true_false_1["statements"]["c"]),
        )

    def test_word_math_keeps_functions_and_superscripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_docx_exam(self.sample_path, assets_dir=Path(tmp) / "assets")

        sections = {section["type"]: section for section in parsed["sections"]}
        true_false_3 = _question(sections["true_false"], 3)

        self.assertEqual(
            [r"f(x)=3(\sin x)^{3}", r"g(x)=-5\cos \left(2x+\frac{\pi }{3}\right)"],
            _math_blocks(true_false_3["prompt_blocks"]),
        )

    def test_word_math_keeps_true_false_question_4_conditions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_docx_exam(self.sample_path, assets_dir=Path(tmp) / "assets")

        sections = {section["type"]: section for section in parsed["sections"]}
        true_false_4 = _question(sections["true_false"], 4)

        self.assertEqual(
            r"x\ne \frac{\pi }{3}+k\frac{\pi }{2}(k\in \mathbb{Z})",
            _math_text(true_false_4["statements"]["a"]),
        )
        self.assertEqual(
            r"\Leftrightarrow x+\frac{\pi }{3}\ne k\pi (k\in \mathbb{Z})",
            _math_text(true_false_4["statements"]["b"]),
        )
        self.assertEqual(
            r"D=\mathbb{R}\setminus \{2k\pi \mid k\in \mathbb{Z}\}",
            _math_text(true_false_4["statements"]["c"]),
        )
        self.assertEqual(
            r"D=\mathbb{R}\setminus \left\{\frac{\pi }{8}+k\frac{\pi }{3}\mid k\in \mathbb{Z}\right\}",
            _math_text(true_false_4["statements"]["d"]),
        )

    def test_math_blocks_use_utf8_safe_markup_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parsed = parse_docx_exam(self.sample_path, assets_dir=Path(tmp) / "assets")

        sections = {section["type"]: section for section in parsed["sections"]}
        question_11 = _question(sections["single_choice"], 11)
        tokens = [part.split("$]", 1)[0] for part in question_11["prompt_markup"].split("[math64:$")[1:]]
        decoded = [
            base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode("utf-8")
            for token in tokens
        ]

        self.assertEqual(_math_blocks(question_11["prompt_blocks"]), decoded)

    def test_section_headings_accept_roman_and_arabic_numbers(self) -> None:
        expected = {
            "single_choice": ("PHẦN I", "PHẦN 1"),
            "true_false": ("PHẦN II", "PHẦN 2"),
            "short_answer": ("PHẦN III", "PHẦN 3"),
        }

        for section_type, headings in expected.items():
            for heading in headings:
                with self.subTest(heading=heading):
                    self.assertEqual(
                        section_type,
                        docx_parser._section_type_from_heading(f"{heading}. Nội dung"),
                    )

    def test_word_math_handles_set_separator_and_absolute_value_delimiters(self) -> None:
        separator = _omml_element(
            """
            <m:d>
              <m:dPr><m:begChr m:val=""/><m:endChr m:val="|"/></m:dPr>
              <m:e><m:r><m:t>x∈ℤ</m:t></m:r></m:e>
            </m:d>
            """
        )
        absolute_value = _omml_element(
            """
            <m:d>
              <m:dPr><m:begChr m:val="|"/><m:endChr m:val="|"/></m:dPr>
              <m:e><m:r><m:t>x</m:t></m:r></m:e>
            </m:d>
            """
        )

        self.assertEqual(r"x\in \mathbb{Z}\mid ", docx_parser._omml_node_to_latex(separator))
        self.assertEqual(
            r"\left\lvert x\right\rvert",
            docx_parser._omml_node_to_latex(absolute_value),
        )

    def test_word_math_handles_one_sided_delimiters_and_legacy_font_noise(self) -> None:
        right_parenthesis = _omml_element(
            """
            <m:d>
              <m:dPr><m:begChr m:val=""/></m:dPr>
              <m:e><m:r><m:t>0;1</m:t></m:r></m:e>
            </m:d>
            """
        )
        self.assertEqual("0;1)", docx_parser._omml_node_to_latex(right_parenthesis))
        self.assertEqual("N", docx_parser._strip_private_use_characters("N\uf700\uf8e6"))
        self.assertEqual("(I) C", docx_parser._math_text_to_latex("(I)\u2004C"))


def _question(section: dict, number: int) -> dict:
    return next(question for question in section["questions"] if question["number"] == number)


def _math_blocks(blocks: list[dict]) -> list[str]:
    return [block["latex"] for block in blocks if block.get("type") == "math"]


def _math_text(blocks: list[dict]) -> str:
    return "".join(_math_blocks(blocks))


def _omml_element(xml: str) -> ET.Element:
    namespace = "http://schemas.openxmlformats.org/officeDocument/2006/math"
    wrapper = ET.fromstring(f'<root xmlns:m="{namespace}">{xml}</root>')
    return wrapper[0]


if __name__ == "__main__":
    unittest.main()
