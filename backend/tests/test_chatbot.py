from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.main import _markup_to_chat_text
from backend.app.services.chatbot import _extract_gemini_text, _extract_openai_text


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


if __name__ == "__main__":
    unittest.main()
