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
    "Mac dinh hay giai thich dua tren dap an he thong, khong tu kiem tra lai moi cau. "
    "Chi khi hoc sinh thac mac tinh dung sai cua dap an, cho rang dap an cua em moi dung, "
    "chi ra dap an he thong sai, hoac dua ra lap luan mau thuan voi dap an he thong, "
    "hay tu giai bai doc lap tu dau va so sanh ket qua, khong mac dinh dap an he thong luon dung. "
    "Neu ket qua doc lap khac dap an he thong, hay noi ro dap an he thong co the chua chinh xac, "
    "trinh bay lap luan va khuyen hoc sinh bao giao vien kiem tra lai. "
    "Neu de bai hoac hinh anh khong du de kiem chung, hay noi ro gioi han thay vi doan. "
    "Khong tu thay doi diem hay khang dinh diem da duoc sua. "
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
    gemini_api_keys: tuple[str, ...] | list[str] = (),
    gemini_model: str = "gemini-3.1-flash-lite",
    openrouter_api_key: str = "",
    openrouter_model: str = "nvidia/nemotron-nano-12b-v2-vl:free",
    nvidia_api_key: str = "",
    nvidia_model: str = "nvidia/nemotron-3-nano-30b-a3b",
    system_prompt: str = SYSTEM_PROMPT,
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
        return _ask_gemini_fallback(
            message=cleaned_message,
            context=context,
            history=safe_history,
            api_keys=_gemini_key_chain(gemini_api_key, gemini_api_keys),
            model=gemini_model,
            system_prompt=system_prompt,
        )
    if provider == "openai":
        return _ask_openai(
            message=cleaned_message,
            context=context,
            history=safe_history,
            api_key=openai_api_key,
            model=openai_model,
            system_prompt=system_prompt,
        )
    if provider == "openrouter":
        return _ask_openrouter(
            message=cleaned_message,
            context=context,
            history=safe_history,
            api_key=openrouter_api_key,
            model=openrouter_model,
            system_prompt=system_prompt,
        )
    if provider == "nvidia":
        return _ask_nvidia(
            message=cleaned_message,
            context=context,
            history=safe_history,
            api_key=nvidia_api_key,
            model=nvidia_model,
            system_prompt=system_prompt,
        )
    raise ValueError(f"AI_PROVIDER khong ho tro: {provider}. Hay dung openai, gemini, openrouter hoac nvidia.")


def _ask_gemini(
    *,
    message: str,
    context: str,
    history: list[dict[str, str]],
    api_key: str,
    model: str,
    system_prompt: str,
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
                            f"{system_prompt}\n\n"
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


def _ask_gemini_fallback(
    *,
    message: str,
    context: str,
    history: list[dict[str, str]],
    api_keys: tuple[str, ...],
    model: str,
    system_prompt: str,
) -> str:
    if not api_keys:
        raise ValueError("GEMINI_API_KEY chua duoc cau hinh.")
    errors: list[str] = []
    for api_key in api_keys:
        try:
            return _ask_gemini(
                message=message,
                context=context,
                history=history,
                api_key=api_key,
                model=model,
                system_prompt=system_prompt,
            )
        except RuntimeError as exc:
            errors.append(str(exc))
            if not _is_retryable_ai_error(exc):
                raise
    raise RuntimeError(f"Tat ca Gemini chatbot key deu loi tam thoi/quota. Loi cuoi: {errors[-1]}")


def _ask_openai(
    *,
    message: str,
    context: str,
    history: list[dict[str, str]],
    api_key: str,
    model: str,
    system_prompt: str,
) -> str:
    if not api_key.strip():
        raise ValueError("OPENAI_API_KEY chua duoc cau hinh.")
    input_messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
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


def _ask_openrouter(
    *,
    message: str,
    context: str,
    history: list[dict[str, str]],
    api_key: str,
    model: str,
    system_prompt: str,
) -> str:
    if not api_key.strip():
        raise ValueError("OPENROUTER_API_KEY chua duoc cau hinh.")
    messages = _chat_completion_messages(message, context, history, system_prompt)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 700,
    }
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://learning-with-mom.local",
            "X-Title": "Hoc cung co Tuyet",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter chatbot loi {exc.code}: {detail[:800]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Khong ket noi duoc OpenRouter chatbot: {exc.reason}") from exc

    text = _extract_chat_completion_text(data)
    if not text:
        raise RuntimeError("OpenRouter chatbot khong tra ve noi dung.")
    return text


def _ask_nvidia(
    *,
    message: str,
    context: str,
    history: list[dict[str, str]],
    api_key: str,
    model: str,
    system_prompt: str,
) -> str:
    if not api_key.strip():
        raise ValueError("NVIDIA_API_KEY chua duoc cau hinh.")
    messages = _chat_completion_messages(message, context, history, system_prompt)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 700,
    }
    request = urllib.request.Request(
        "https://integrate.api.nvidia.com/v1/chat/completions",
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
        raise RuntimeError(f"NVIDIA chatbot loi {exc.code}: {detail[:800]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Khong ket noi duoc NVIDIA chatbot: {exc.reason}") from exc

    text = _extract_chat_completion_text(data)
    if not text:
        raise RuntimeError("NVIDIA chatbot khong tra ve noi dung.")
    return text


def _chat_completion_messages(
    message: str,
    context: str,
    history: list[dict[str, str]],
    system_prompt: str,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"# Ngu canh cau hoi\n{context}"},
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": message})
    return messages


def _history_text(history: list[dict[str, str]]) -> str:
    if not history:
        return "(chua co)"
    return "\n".join(f"{item['role']}: {item['content']}" for item in history)


def _gemini_key_chain(primary_key: str, extra_keys: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    keys: list[str] = []
    for key in [primary_key, *extra_keys]:
        cleaned = str(key).strip()
        if cleaned and cleaned not in keys:
            keys.append(cleaned)
    return tuple(keys)


def _is_retryable_ai_error(exc: RuntimeError) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in (" 429", "quota", "rate", "resource_exhausted", " 503", "unavailable"))


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


def _extract_chat_completion_text(data: dict[str, Any]) -> str:
    parts: list[str] = []
    for choice in data.get("choices", []):
        message = choice.get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
    return "\n".join(parts).strip()
