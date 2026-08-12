from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.main import _friendly_ai_error_message, _markup_to_chat_text
from backend.app.services.chatbot import (
    _extract_chat_completion_text,
    _extract_gemini_text,
    _extract_openai_text,
    _gemini_key_chain,
)


class ChatbotHelpersTest(unittest.TestCase):
    def test_markup_to_chat_text_decodes_math64(self) -> None:
        text = _markup_to_chat_text("Tinh [math64:$eCsx$] va [img:$img_0001$]")

        self.assertIn("\\(x+1\\)", text)
        self.assertIn("anh cong thuc img_0001", text)

    def test_extract_gemini_text(self) -> None:
        payload = {"candidates": [{"content": {"parts": [{"text": "Giai thich ngan gon."}]}}]}

        self.assertEqual("Giai thich ngan gon.", _extract_gemini_text(payload))

    def test_extract_openai_text_from_output_text(self) -> None:
        self.assertEqual("OK", _extract_openai_text({"output_text": "OK"}))

    def test_extract_chat_completion_text(self) -> None:
        payload = {"choices": [{"message": {"content": "Giai thich ngan gon."}}]}

        self.assertEqual("Giai thich ngan gon.", _extract_chat_completion_text(payload))

    def test_gemini_key_chain_dedupes_primary_and_fallback_keys(self) -> None:
        self.assertEqual(("main", "backup"), _gemini_key_chain("main", ["backup", "main"]))

    def test_friendly_ai_error_hides_raw_api_payload(self) -> None:
        message = _friendly_ai_error_message(
            RuntimeError('Gemini chatbot loi 400: {"reason":"API_KEY_INVALID","message":"API key not valid."}')
        )

        self.assertIn("API key", message)
        self.assertNotIn("googleapis", message)
        self.assertNotIn("API_KEY_INVALID", message)


if __name__ == "__main__":
    unittest.main()
