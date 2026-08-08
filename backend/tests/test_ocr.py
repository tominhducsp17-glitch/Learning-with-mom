from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.ocr import (
    _extract_gemini_text,
    _extract_output_text,
    _gemini_key_chain,
    _parse_batch_suggestions,
    _parse_suggestion,
)


class OcrSuggestionParsingTest(unittest.TestCase):
    def test_extract_output_text_from_responses_payload(self) -> None:
        payload = {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"latex":"x^2 + 1","confidence":0.92,"notes":"","needs_review":true}',
                        }
                    ]
                }
            ]
        }

        self.assertIn("x^2 + 1", _extract_output_text(payload))

    def test_extract_text_from_gemini_payload(self) -> None:
        payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"latex":"a^2+b^2","confidence":0.87,"notes":"","needs_review":true}'
                            }
                        ]
                    }
                }
            ]
        }

        self.assertIn("a^2+b^2", _extract_gemini_text(payload))

    def test_parse_json_suggestion(self) -> None:
        suggestion = _parse_suggestion('{"latex":"\\\\frac{x-2}{3}","confidence":0.8,"notes":"ok"}')

        self.assertEqual("\\frac{x-2}{3}", suggestion["latex"])
        self.assertEqual(0.8, suggestion["confidence"])
        self.assertTrue(suggestion["needs_review"])

    def test_parse_json_array_suggestion(self) -> None:
        suggestion = _parse_suggestion('[{"latex":"Oxyz","confidence":0.7,"notes":"single token"}]')

        self.assertEqual("Oxyz", suggestion["latex"])
        self.assertEqual(0.7, suggestion["confidence"])

    def test_parse_batch_suggestions(self) -> None:
        suggestions = _parse_batch_suggestions(
            '[{"asset_id":"img_0001","latex":"Oxyz","confidence":1},'
            '{"asset_id":"img_0002","latex":"\\\\begin{cases}x=1\\\\\\\\y=2\\\\end{cases}","confidence":0.9}]'
        )

        self.assertEqual("Oxyz", suggestions["img_0001"]["latex"])
        self.assertIn("\\begin{cases}", suggestions["img_0002"]["latex"])

    def test_parse_batch_suggestions_from_wrapped_text(self) -> None:
        suggestions = _parse_batch_suggestions(
            'Here are the results:\n```json\n'
            '[{"asset_id":"img_0141","latex":"x+y","confidence":0.9}]'
            '\n```'
        )

        self.assertEqual("x+y", suggestions["img_0141"]["latex"])

    def test_parse_non_json_fallback(self) -> None:
        suggestion = _parse_suggestion("\\sqrt{x}")

        self.assertEqual("\\sqrt{x}", suggestion["latex"])
        self.assertLess(suggestion["confidence"], 0.5)
        self.assertTrue(suggestion["needs_review"])

    def test_gemini_key_chain_dedupes_primary_and_fallback_keys(self) -> None:
        self.assertEqual(("main", "backup"), _gemini_key_chain(" main ", ("backup", "main", "")))


if __name__ == "__main__":
    unittest.main()
