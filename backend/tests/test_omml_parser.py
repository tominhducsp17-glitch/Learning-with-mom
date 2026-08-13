from __future__ import annotations

import base64
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.parser import parse_docx_exam


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


def _question(section: dict, number: int) -> dict:
    return next(question for question in section["questions"] if question["number"] == number)


def _math_blocks(blocks: list[dict]) -> list[str]:
    return [block["latex"] for block in blocks if block.get("type") == "math"]


def _math_text(blocks: list[dict]) -> str:
    return "".join(_math_blocks(blocks))


if __name__ == "__main__":
    unittest.main()
