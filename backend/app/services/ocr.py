from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


SUPPORTED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}


OCR_PROMPT = (
    "Ban la cong cu OCR cong thuc Toan cho de thi THPT Viet Nam. "
    "Hay doc CHI bieu thuc toan trong anh va tra ve JSON hop le. "
    "Khong giai bai, khong them loi giai. "
    "Truong latex la LaTeX khong boc trong dau $. "
    "BAT BUOC giu dung cau truc khong gian cua cong thuc: "
    "he phuong trinh hoac nhieu dong phai dung \\begin{cases} ... \\\\ ... \\end{cases} "
    "hoac \\begin{aligned} ... \\\\ ... \\end{aligned}; "
    "khong duoc gop cac dong thanh mot hang ngang. "
    "Ma tran/vector cot/bang can dung bmatrix, pmatrix, array hoac aligned phu hop. "
    "Neu anh mo hoac khong chac, dat confidence thap va ghi ro trong notes. "
    'Schema: {"latex":"string","confidence":0.0,"notes":"string","needs_review":true}'
)


def suggest_latex_for_image(
    image_path: Path,
    provider: str,
    *,
    openai_api_key: str = "",
    openai_model: str = "gpt-5-mini",
    gemini_api_key: str = "",
    gemini_api_keys: tuple[str, ...] | list[str] = (),
    gemini_model: str = "gemini-3.1-flash-lite",
    openrouter_api_key: str = "",
    openrouter_model: str = "nvidia/nemotron-nano-12b-v2-vl:free",
    nvidia_api_key: str = "",
    nvidia_model: str = "nvidia/nemotron-ocr-v2",
    nvidia_base_url: str = "",
) -> dict[str, Any]:
    if not image_path.is_file():
        raise FileNotFoundError(str(image_path))

    mime_type = mimetypes.guess_type(image_path.name)[0] or ""
    if mime_type not in SUPPORTED_IMAGE_TYPES:
        raise ValueError(f"Khong ho tro OCR truc tiep dinh dang {image_path.suffix or image_path.name}.")

    image_bytes = image_path.read_bytes()
    image_base64 = base64.b64encode(image_bytes).decode("ascii")

    if provider == "gemini":
        return _suggest_latex_with_gemini_fallback(
            image_base64,
            mime_type,
            _gemini_key_chain(gemini_api_key, gemini_api_keys),
            gemini_model,
        )
    if provider == "openai":
        return _suggest_latex_with_openai(image_base64, mime_type, openai_api_key, openai_model)
    if provider == "openrouter":
        return _suggest_latex_with_openrouter(image_base64, mime_type, openrouter_api_key, openrouter_model)
    if provider == "nvidia":
        return _suggest_latex_with_nvidia_ocr(image_base64, mime_type, nvidia_api_key, nvidia_model, nvidia_base_url)
    raise ValueError(f"AI_PROVIDER khong ho tro: {provider}. Hay dung openai, gemini, openrouter hoac nvidia.")


def suggest_latex_for_image_batch(
    images: list[tuple[str, Path]],
    provider: str,
    *,
    openai_api_key: str = "",
    openai_model: str = "gpt-5-mini",
    gemini_api_key: str = "",
    gemini_api_keys: tuple[str, ...] | list[str] = (),
    gemini_model: str = "gemini-3.1-flash-lite",
    openrouter_api_key: str = "",
    openrouter_model: str = "nvidia/nemotron-nano-12b-v2-vl:free",
    nvidia_api_key: str = "",
    nvidia_model: str = "nvidia/nemotron-ocr-v2",
    nvidia_base_url: str = "",
) -> dict[str, dict[str, Any]]:
    if not images:
        return {}
    if provider != "gemini":
        return {
            asset_id: suggest_latex_for_image(
                image_path,
                provider,
                openai_api_key=openai_api_key,
                openai_model=openai_model,
                gemini_api_key=gemini_api_key,
                gemini_api_keys=gemini_api_keys,
                gemini_model=gemini_model,
                openrouter_api_key=openrouter_api_key,
                openrouter_model=openrouter_model,
                nvidia_api_key=nvidia_api_key,
                nvidia_model=nvidia_model,
                nvidia_base_url=nvidia_base_url,
            )
            for asset_id, image_path in images
        }
    return _suggest_latex_batch_with_gemini_fallback(
        images,
        _gemini_key_chain(gemini_api_key, gemini_api_keys),
        gemini_model,
    )


def math_replacement_token(latex: str) -> str:
    encoded = base64.urlsafe_b64encode(latex.strip().encode("utf-8")).decode("ascii").rstrip("=")
    return f"[math64:${encoded}$]"


def _suggest_latex_with_openai(image_base64: str, mime_type: str, api_key: str, model: str) -> dict[str, Any]:
    if not api_key.strip():
        raise ValueError("OPENAI_API_KEY chua duoc cau hinh.")
    data_url = f"data:{mime_type};base64,{image_base64}"
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": OCR_PROMPT,
                    },
                    {
                        "type": "input_image",
                        "image_url": data_url,
                        "detail": "high",
                    },
                ],
            }
        ],
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
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI OCR loi {exc.code}: {detail[:800]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Khong ket noi duoc OpenAI OCR: {exc.reason}") from exc

    raw_text = _extract_output_text(data)
    suggestion = _parse_suggestion(raw_text)
    suggestion["raw_text"] = raw_text
    return suggestion


def _suggest_latex_with_openrouter(image_base64: str, mime_type: str, api_key: str, model: str) -> dict[str, Any]:
    if not api_key.strip():
        raise ValueError("OPENROUTER_API_KEY chua duoc cau hinh.")
    data_url = f"data:{mime_type};base64,{image_base64}"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": OCR_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "temperature": 0,
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
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter OCR loi {exc.code}: {detail[:800]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Khong ket noi duoc OpenRouter OCR: {exc.reason}") from exc

    raw_text = _extract_chat_completion_text(data)
    suggestion = _parse_suggestion(raw_text)
    suggestion["raw_text"] = raw_text
    return suggestion


def _suggest_latex_with_nvidia_ocr(
    image_base64: str,
    mime_type: str,
    api_key: str,
    model: str,
    base_url: str,
) -> dict[str, Any]:
    if not base_url.strip():
        raise ValueError("NVIDIA_OCR_BASE_URL chua duoc cau hinh.")
    endpoint = base_url.strip().rstrip("/") + "/v1/ocr"
    data_url = f"data:{mime_type};base64,{image_base64}"
    payload = {
        "model": model,
        "input": [{"type": "image_url", "url": data_url}],
        "merge_levels": ["word"],
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"NVIDIA OCR loi {exc.code}: {detail[:800]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Khong ket noi duoc NVIDIA OCR: {exc.reason}") from exc

    raw_text = _extract_nvidia_ocr_text(data)
    if not raw_text:
        raise RuntimeError("NVIDIA OCR khong tra ve noi dung.")
    return {
        "latex": raw_text,
        "confidence": 0.4,
        "notes": "NVIDIA OCR fallback tra ve text OCR tho; giao vien nen kiem tra truoc khi dung.",
        "needs_review": True,
        "raw_text": raw_text,
    }


def _suggest_latex_with_gemini(image_base64: str, mime_type: str, api_key: str, model: str) -> dict[str, Any]:
    if not api_key.strip():
        raise ValueError("GEMINI_API_KEY chua duoc cau hinh.")
    model_name = model.split("/", 1)[1] if model.startswith("models/") else model
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(model_name, safe='-_.')}:generateContent"
        f"?key={urllib.parse.quote(api_key, safe='')}"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": OCR_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": image_base64,
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini OCR loi {exc.code}: {detail[:800]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Khong ket noi duoc Gemini OCR: {exc.reason}") from exc

    raw_text = _extract_gemini_text(data)
    suggestion = _parse_suggestion(raw_text)
    suggestion["raw_text"] = raw_text
    return suggestion


def _suggest_latex_with_gemini_fallback(
    image_base64: str,
    mime_type: str,
    api_keys: tuple[str, ...],
    model: str,
) -> dict[str, Any]:
    if not api_keys:
        raise ValueError("GEMINI_API_KEY chua duoc cau hinh.")
    errors: list[str] = []
    for index, api_key in enumerate(api_keys, start=1):
        try:
            result = _suggest_latex_with_gemini(image_base64, mime_type, api_key, model)
            result["api_key_index"] = index
            return result
        except RuntimeError as exc:
            errors.append(str(exc))
            if not _is_retryable_ai_error(exc):
                raise
    raise RuntimeError(f"Tat ca Gemini OCR key deu loi tam thoi/quota. Loi cuoi: {errors[-1]}")


def _suggest_latex_batch_with_gemini(
    images: list[tuple[str, Path]],
    api_key: str,
    model: str,
) -> dict[str, dict[str, Any]]:
    if not api_key.strip():
        raise ValueError("GEMINI_API_KEY chua duoc cau hinh.")
    model_name = model.split("/", 1)[1] if model.startswith("models/") else model
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(model_name, safe='-_.')}:generateContent"
        f"?key={urllib.parse.quote(api_key, safe='')}"
    )
    parts: list[dict[str, Any]] = [
        {
            "text": (
                OCR_PROMPT
                + " Ban se nhan nhieu anh. Truoc moi anh co asset_id rieng. "
                "Hay tra ve JSON ARRAY, moi phan tu co asset_id dung voi anh do: "
                '[{"asset_id":"img_0001","latex":"...","confidence":0.0,"notes":"string","needs_review":true}]. '
                "Khong bo sot asset_id nao."
            )
        }
    ]
    for asset_id, image_path in images:
        mime_type = mimetypes.guess_type(image_path.name)[0] or ""
        if mime_type not in SUPPORTED_IMAGE_TYPES:
            raise ValueError(f"{asset_id}: Khong ho tro OCR truc tiep dinh dang {image_path.suffix or image_path.name}.")
        image_base64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        parts.append({"text": f"asset_id: {asset_id}"})
        parts.append(
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": image_base64,
                }
            }
        )

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini batch OCR loi {exc.code}: {detail[:800]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Khong ket noi duoc Gemini batch OCR: {exc.reason}") from exc

    raw_text = _extract_gemini_text(data)
    return _parse_batch_suggestions(raw_text)


def _suggest_latex_batch_with_gemini_fallback(
    images: list[tuple[str, Path]],
    api_keys: tuple[str, ...],
    model: str,
) -> dict[str, dict[str, Any]]:
    if not api_keys:
        raise ValueError("GEMINI_API_KEY chua duoc cau hinh.")
    errors: list[str] = []
    for index, api_key in enumerate(api_keys, start=1):
        try:
            results = _suggest_latex_batch_with_gemini(images, api_key, model)
            for suggestion in results.values():
                suggestion["api_key_index"] = index
            return results
        except RuntimeError as exc:
            errors.append(str(exc))
            if not _is_retryable_ai_error(exc):
                raise
    raise RuntimeError(f"Tat ca Gemini batch OCR key deu loi tam thoi/quota. Loi cuoi: {errors[-1]}")


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


def _extract_output_text(data: dict[str, Any]) -> str:
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


def _extract_nvidia_ocr_text(data: dict[str, Any]) -> str:
    tokens: list[str] = []
    for item in data.get("data", []):
        detections = item.get("text_detections", [])
        for detection in detections:
            prediction = detection.get("text_prediction", {})
            text = prediction.get("text")
            if isinstance(text, str) and text.strip():
                tokens.append(text.strip())
    if tokens:
        return " ".join(tokens).strip()
    if isinstance(data.get("text"), str):
        return data["text"].strip()
    return ""


def _parse_suggestion(raw_text: str) -> dict[str, Any]:
    cleaned = _strip_code_fence(raw_text)
    cleaned = _extract_json_candidate(cleaned)
    if cleaned is None:
        cleaned = raw_text.strip()
        return {
            "latex": cleaned,
            "confidence": 0.3,
            "notes": "Model khong tra ve JSON hop le, can giao vien kiem tra ky.",
            "needs_review": True,
        }
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "latex": raw_text.strip(),
            "confidence": 0.3,
            "notes": "Model khong tra ve JSON hop le, can giao vien kiem tra ky.",
            "needs_review": True,
        }

    return _normalize_single_suggestion(data, raw_text.strip())


def _strip_code_fence(raw_text: str) -> str:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    return cleaned


def _extract_json_candidate(text: str) -> str | None:
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped
    array_start = stripped.find("[")
    array_end = stripped.rfind("]")
    if 0 <= array_start < array_end:
        return stripped[array_start:array_end + 1]
    object_start = stripped.find("{")
    object_end = stripped.rfind("}")
    if 0 <= object_start < object_end:
        return stripped[object_start:object_end + 1]
    return None


def _normalize_single_suggestion(data: Any, fallback_text: str) -> dict[str, Any]:
    try:
        if isinstance(data, list):
            first_item = next((item for item in data if isinstance(item, dict)), None)
            if first_item is None:
                return {
                    "latex": fallback_text,
                    "confidence": 0.3,
                    "notes": "Model tra ve JSON array nhung khong co object hop le, can giao vien kiem tra ky.",
                    "needs_review": True,
                }
            data = first_item
        if not isinstance(data, dict):
            return {
                "latex": fallback_text,
                "confidence": 0.3,
                "notes": "Model tra ve JSON khong dung schema, can giao vien kiem tra ky.",
                "needs_review": True,
            }

        latex = str(data.get("latex", "")).strip()
        confidence = data.get("confidence", 0.5)
        try:
            confidence_value = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence_value = 0.5
        return {
            "latex": latex,
            "confidence": confidence_value,
            "notes": str(data.get("notes", "")).strip(),
            "needs_review": bool(data.get("needs_review", True)),
        }
    except (TypeError, ValueError):
        return {
            "latex": fallback_text,
            "confidence": 0.3,
            "notes": "Khong chuan hoa duoc ket qua OCR, can giao vien kiem tra ky.",
            "needs_review": True,
        }


def _parse_batch_suggestions(raw_text: str) -> dict[str, dict[str, Any]]:
    cleaned = _strip_code_fence(raw_text)
    cleaned = _extract_json_candidate(cleaned)
    if cleaned is None:
        raise RuntimeError("Model khong tra ve JSON batch hop le.")
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Model khong tra ve JSON batch hop le.") from exc

    if isinstance(data, dict):
        for key in ("results", "items", "assets"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            mapped: dict[str, dict[str, Any]] = {}
            for asset_id, value in data.items():
                if isinstance(value, dict):
                    item = dict(value)
                    item["asset_id"] = asset_id
                    mapped[asset_id] = _normalize_batch_item(item)
                elif isinstance(value, str):
                    mapped[asset_id] = _normalize_batch_item({"asset_id": asset_id, "latex": value})
            return mapped

    if not isinstance(data, list):
        raise RuntimeError("Model tra ve JSON batch khong dung schema.")

    results: dict[str, dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        asset_id = str(item.get("asset_id") or item.get("id") or "").strip()
        if asset_id:
            results[asset_id] = _normalize_batch_item(item)
    return results


def _normalize_batch_item(item: dict[str, Any]) -> dict[str, Any]:
    suggestion = _normalize_single_suggestion(item, "")
    suggestion["asset_id"] = str(item.get("asset_id") or item.get("id") or "").strip()
    return suggestion
