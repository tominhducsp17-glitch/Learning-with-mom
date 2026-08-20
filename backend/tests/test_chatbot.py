from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.main import _friendly_ai_error_message, _markup_to_chat_text
from backend.app.services.chatbot import (
    SYSTEM_PROMPT,
    _ask_tokenrouter,
    _extract_chat_completion_text,
    _extract_gemini_text,
    _extract_openai_text,
    _gemini_key_chain,
)


class ChatbotHelpersTest(unittest.TestCase):
    def test_system_prompt_only_rechecks_when_student_challenges_answer(self) -> None:
        self.assertIn("Mac dinh hay giai thich dua tren dap an he thong", SYSTEM_PROMPT)
        self.assertIn("Chi khi hoc sinh thac mac tinh dung sai cua dap an", SYSTEM_PROMPT)
        self.assertIn("hay tu giai bai doc lap tu dau", SYSTEM_PROMPT)
        self.assertIn("dap an he thong co the chua chinh xac", SYSTEM_PROMPT)
        self.assertIn("Khong tu thay doi diem", SYSTEM_PROMPT)

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

    def test_friendly_ai_error_recognizes_credit_exhaustion_before_http_403(self) -> None:
        message = _friendly_ai_error_message(
            RuntimeError("TokenRouter chatbot loi 403: insufficient_user_quota; credit limit $0; recharge")
        )

        self.assertIn("hết credit", message)
        self.assertNotIn("API key", message)

    @patch("backend.app.services.chatbot.urllib.request.urlopen")
    def test_tokenrouter_uses_openai_compatible_chat_endpoint(self, urlopen) -> None:
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = b'{"choices":[{"message":{"content":"Dung roi."}}]}'

        answer = _ask_tokenrouter(
            message="Tai sao?",
            context="Cau hoi tap hop.",
            history=[],
            api_key="secret",
            base_url="https://api.tokenrouter.com/v1/",
            model="deepseek/deepseek-v4-flash",
            system_prompt="Giai thich ngan gon.",
        )

        request = urlopen.call_args.args[0]
        self.assertEqual("Dung roi.", answer)
        self.assertEqual("https://api.tokenrouter.com/v1/chat/completions", request.full_url)
        self.assertIn(b'"model": "deepseek/deepseek-v4-flash"', request.data)
        self.assertEqual("Bearer secret", request.get_header("Authorization"))


if __name__ == "__main__":
    unittest.main()
