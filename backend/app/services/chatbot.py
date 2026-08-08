from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


SYSTEM_PROMPT = (
    "Ban la tro ly hoc Toan THPT sau khi hoc sinh da nop bai. "
    "Chi su dung noi dung cau hoi, dap an dung va bai lam hoc sinh duoc cung cap. "
    "Giai thich ngan gon, than thien, theo tung buoc vua du de hoc sinh tu hieu. "
    "Khong thay doi diem, khong phan quyet lai ket qua cham. "
    "Neu hoc sinh hoi ngoai cau hoi hien tai, hay nhe nhang dua ve cau hoi dang xem. "
    "Cong thuc duoc viet bang LaTeX, khong can boc trong dau dollar."
)


def ask_chatbot(
    *,
    provider: str,
    message: str,
    context: str,
    history: list[dict[str, str]] | None = None,
    openai_api_key: str = "",
    openai_model: str = "gpt-5-mini",
    gemini_api_key: str = "",
    gemini_model: str = "gemini-3.1-flash-lite",
) -> str:
    cleaned_message = " ".join(message.strip().split())
    if not cleaned_message:
        raise ValueError("Cau hoi khong duoc de trong.")
    if len(cleaned_message) > 1200:
        raise ValueError("Cau hoi qua dai. Hay hoi ngan gon hon.")

    safe_history = [
        {
            "role": "assistant" if item.get("role") == "assistant" else "user",
            "content": str(item.get("content", ""))[:1200],
        }
        for item in (history or [])[-6:]
        if str(item.get("content", "")).strip()
    ]

    if provider == "gemini":
        return _ask_gemini(
            message=cleaned_message,
            context=context,
            history=safe_history,
            api_key=gemini_api_key,
            model=gemini_model,
        )
    if provider == "openai":
        return _ask_openai(
            message=cleaned_message,
            context=context,
            history=safe_history,
            api_key=openai_api_key,
            model=openai_model,
        )
    raise ValueError(f"AI_PROVIDER khong ho tro: {provider}. Hay dung openai hoac gemini.")


def _ask_gemini(
    *,
    message: str,
    context: str,
    history: list[dict[str, str]],
    api_key: str,
    model: str,
) -> str:
    if not api_key.strip():
        raise ValueError("GEMINI_API_KEY chua duoc cau hinh.")
    model_name = model.split("/", 1)[1] if model.startswith("models/") else model
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(model_name, safe='-_.')}:generateContent"
        f"?key={urllib.parse.quote(api_key, safe='')}"
    )
    history_text = _history_text(history)
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            f"{SYSTEM_PROMPT}\n\n"
                            f"# Ngu canh cau hoi\n{context}\n\n"
                            f"# Lich su gan day\n{history_text}\n\n"
                            f"# Hoc sinh hoi\n{message}"
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 700,
        },
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini chatbot loi {exc.code}: {detail[:800]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Khong ket noi duoc Gemini chatbot: {exc.reason}") from exc

    text = _extract_gemini_text(data)
    if not text:
        raise RuntimeError("Gemini chatbot khong tra ve noi dung.")
    return text


def _ask_openai(
    *,
    message: str,
    context: str,
    history: list[dict[str, str]],
    api_key: str,
    model: str,
) -> str:
    if not api_key.strip():
        raise ValueError("OPENAI_API_KEY chua duoc cau hinh.")
    input_messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"# Ngu canh cau hoi\n{context}"},
    ]
    input_messages.extend(history)
    input_messages.append({"role": "user", "content": message})
    payload = {
        "model": model,
        "input": input_messages,
        "max_output_tokens": 700,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI chatbot loi {exc.code}: {detail[:800]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Khong ket noi duoc OpenAI chatbot: {exc.reason}") from exc

    text = _extract_openai_text(data)
    if not text:
        raise RuntimeError("OpenAI chatbot khong tra ve noi dung.")
    return text


def _history_text(history: list[dict[str, str]]) -> str:
    if not history:
        return "(chua co)"
    return "\n".join(f"{item['role']}: {item['content']}" for item in history)


def _extract_gemini_text(data: dict[str, Any]) -> str:
    parts: list[str] = []
    for candidate in data.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def _extract_openai_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"].strip()

    parts: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()
