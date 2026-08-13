from __future__ import annotations

import base64
import csv
import io
import os
import re
import shutil
import subprocess
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4
from xml.sax.saxutils import escape

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.app.config import get_settings
from backend.app.services.chatbot import ask_chatbot
from backend.app.services.grading import grade_exam_submission
from backend.app.services.ocr import math_replacement_token, suggest_latex_for_image, suggest_latex_for_image_batch
from backend.app.services.parser import parse_docx_exam
from backend.app.storage import DraftStore, add_default_scores, section_display


settings = get_settings()

store = DraftStore(settings.database_path)
app = FastAPI(title="Học cùng cô Tuyết", version="0.3.0")


class DraftUpdate(BaseModel):
    exam: dict[str, Any]


class SubmissionUpdate(BaseModel):
    student_id: str
    answers: dict[str, Any]


class StudentPayload(BaseModel):
    name: str
    student_code: str = ""


class ClassroomPayload(BaseModel):
    name: str
    school_year: str = "2026-2027"
    students: list[StudentPayload]


class PublishAssignmentPayload(BaseModel):
    class_id: str
    duration_minutes: int = 45
    show_score: bool = False
    show_answers: bool = False


class AssignmentVisibilityPayload(BaseModel):
    show_score: bool = False
    show_answers: bool = False


class OcrAssetPayload(BaseModel):
    asset_id: str


class ChatMessagePayload(BaseModel):
    role: str
    content: str


class StudentChatPayload(BaseModel):
    student_id: str
    section_type: str
    question_number: int
    message: str
    history: list[ChatMessagePayload] = []


@app.on_event("startup")
def initialize_storage() -> None:
    settings.upload_root.mkdir(parents=True, exist_ok=True)
    settings.asset_root.mkdir(parents=True, exist_ok=True)
    store.initialize()


@app.get("/api/health")
def health() -> dict[str, Any]:
    storage_ok = _path_is_writable(settings.storage_root)
    database_parent_ok = _path_is_writable(settings.database_path.parent)
    converter = _converter_status()
    return {
        "status": "ok" if storage_ok and database_parent_ok else "degraded",
        "env": settings.app_env,
        "storage": {
            "path": str(settings.storage_root),
            "writable": storage_ok,
        },
        "database": {
            "path": str(settings.database_path),
            "parent_writable": database_parent_ok,
        },
        "ai": {
            "provider": settings.ai_provider,
            "provider_chain": settings.ai_provider_chain,
            "chat_provider_chain": settings.chat_provider_chain,
            "auto_ocr_on_import": settings.auto_ocr_on_import,
            "auto_ocr_max_workers": settings.auto_ocr_max_workers,
            "auto_ocr_batch_size": settings.auto_ocr_batch_size,
            "openai_configured": bool(settings.openai_api_key.strip()),
            "gemini_configured": bool(settings.gemini_api_keys),
            "gemini_key_count": len(settings.gemini_api_keys),
            "openrouter_configured": bool(settings.openrouter_api_key.strip()),
            "nvidia_configured": bool(settings.nvidia_api_key.strip()),
            "nvidia_ocr_base_url_configured": bool(settings.nvidia_ocr_base_url),
            "ocr_providers_available": _configured_ocr_providers(),
            "chat_providers_available": _configured_chat_providers(),
            "models": {
                "openai": settings.openai_model,
                "gemini": settings.gemini_model,
                "openrouter_ocr": settings.openrouter_ocr_model,
                "openrouter_chat": settings.openrouter_chat_model,
                "nvidia_ocr": settings.nvidia_ocr_model,
                "nvidia_chat": settings.nvidia_chat_model,
            },
        },
        "public_base_url": settings.public_base_url,
        "converter": converter,
    }


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    return {
        "drafts": store.list_drafts(),
        "assignments": store.list_assignments(),
    }


@app.get("/api/classes")
def list_classes() -> list[dict[str, Any]]:
    return store.list_classes()


@app.post("/api/classes")
def create_classroom(payload: ClassroomPayload) -> dict[str, Any]:
    try:
        return store.upsert_class(
            None,
            payload.name,
            payload.school_year,
            [student.model_dump() for student in payload.students],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.put("/api/classes/{class_id}")
def update_classroom(class_id: str, payload: ClassroomPayload) -> dict[str, Any]:
    try:
        return store.upsert_class(
            class_id,
            payload.name,
            payload.school_year,
            [student.model_dump() for student in payload.students],
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/exams/import")
async def import_exam(file: UploadFile = File(...)) -> dict[str, Any]:
    filename = Path(file.filename or "exam.docx").name
    if Path(filename).suffix.lower() != ".docx":
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file .docx trong giai đoạn này.")

    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File vượt quá giới hạn 25 MB.")

    draft_id = uuid4().hex
    upload_path = settings.upload_root / f"{draft_id}.docx"
    assets_dir = settings.asset_root / draft_id
    upload_path.write_bytes(content)

    try:
        parsed = parse_docx_exam(upload_path, assets_dir=assets_dir, convert_images=True)
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Không thể đọc cấu trúc DOCX: {exc}") from exc

    parsed["source_file"] = filename
    parsed = add_default_scores(parsed)
    if settings.auto_ocr_on_import:
        _auto_ocr_exam_assets(draft_id, parsed)
    draft = store.create(draft_id, filename, parsed)
    return _draft_for_client(draft)


@app.get("/api/exams/{draft_id}")
def get_exam(draft_id: str) -> dict[str, Any]:
    try:
        return _draft_for_client(store.get(draft_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản nháp.") from exc


@app.put("/api/exams/{draft_id}")
def update_exam(draft_id: str, payload: DraftUpdate) -> dict[str, Any]:
    try:
        updated = store.update(draft_id, payload.exam)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản nháp.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _draft_for_client(updated)


@app.post("/api/exams/{draft_id}/assets/ocr")
def suggest_asset_latex(draft_id: str, payload: OcrAssetPayload) -> dict[str, Any]:
    try:
        draft = store.get(draft_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Khong tim thay ban nhap.") from exc

    asset = _find_exam_asset(draft["exam"], payload.asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Khong tim thay anh/cong thuc can OCR.")

    image_path = _asset_image_path(draft_id, asset)
    if not image_path:
        raise HTTPException(status_code=422, detail="Chua co anh PNG/JPEG/WebP/GIF de OCR.")

    try:
        suggestion = _suggest_latex_for_image_with_fallback(image_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Khong tim thay file anh OCR.") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "asset_id": payload.asset_id,
        "source_filename": image_path.name,
        "suggestion": suggestion,
        "replacement_token": math_replacement_token(str(suggestion.get("latex", ""))),
    }


@app.post("/api/exams/{draft_id}/auto-ocr")
def rerun_auto_ocr(draft_id: str) -> dict[str, Any]:
    try:
        draft = store.get(draft_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Khong tim thay ban nhap.") from exc

    exam = deepcopy(draft["exam"])
    _clear_warnings(exam, {"AUTO_OCR_PARTIAL"})
    _auto_ocr_exam_assets(draft_id, exam)
    try:
        updated = store.update(draft_id, exam)
        store.sync_published_exams_for_draft(draft_id, updated["exam"])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Khong tim thay ban nhap.") from exc
    return _draft_for_client(updated)


@app.post("/api/exams/{draft_id}/publish-demo")
def publish_demo_assignment(draft_id: str) -> dict[str, Any]:
    try:
        assignment = store.publish_demo_assignment(draft_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản nháp.") from exc
    return _assignment_for_client(assignment)


@app.post("/api/exams/{draft_id}/publish")
def publish_assignment(draft_id: str, payload: PublishAssignmentPayload) -> dict[str, Any]:
    try:
        assignment = store.publish_assignment(
            draft_id,
            payload.class_id,
            payload.duration_minutes,
            show_score=payload.show_score,
            show_answers=payload.show_answers,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản nháp hoặc lớp.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _assignment_for_client(assignment)


@app.put("/api/assignments/{code}/visibility")
def update_assignment_visibility(code: str, payload: AssignmentVisibilityPayload) -> dict[str, Any]:
    try:
        assignment = store.update_assignment_visibility(code, payload.show_score, payload.show_answers)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài được giao.") from exc
    return _assignment_for_client(assignment)


@app.get("/api/assignments/{code}")
def get_assignment(code: str, student_id: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        assignment = store.get_assignment_by_code(code, include_answers=False, student_id=student_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài được giao.") from exc
    return _assignment_for_client(assignment)


@app.put("/api/assignments/{code}/submission")
def autosave_submission(code: str, payload: SubmissionUpdate) -> dict[str, Any]:
    try:
        return store.save_submission(code, payload.student_id, payload.answers, submit=False)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy học sinh hoặc bài được giao.") from exc


@app.post("/api/assignments/{code}/submit")
def submit_assignment(code: str, payload: SubmissionUpdate) -> dict[str, Any]:
    try:
        return store.save_submission(code, payload.student_id, payload.answers, submit=True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy học sinh hoặc bài được giao.") from exc


@app.post("/api/assignments/{code}/chat")
def student_assignment_chat(code: str, payload: StudentChatPayload) -> dict[str, Any]:
    try:
        assignment = store.get_assignment_by_code(code, include_answers=True, student_id=payload.student_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Khong tim thay hoc sinh hoac bai duoc giao.") from exc

    submission = assignment.get("submission")
    if not submission or submission.get("status") != "submitted":
        raise HTTPException(status_code=403, detail="Chi co the hoi chatbot sau khi da nop bai.")
    if not assignment.get("show_answers"):
        raise HTTPException(status_code=403, detail="Giao vien chua cong bo dap an cho bai nay.")

    question = _find_question(assignment["exam"], payload.section_type, payload.question_number)
    if not question:
        raise HTTPException(status_code=404, detail="Khong tim thay cau hoi.")

    grade = grade_exam_submission(assignment["exam"], submission.get("answers") or {})
    detail = _find_grade_detail(grade, payload.section_type, payload.question_number)
    context = _build_chat_question_context(
        assignment=assignment,
        question=question,
        section_type=payload.section_type,
        detail=detail,
        student_answer=(submission.get("answers") or {}).get(f"{payload.section_type}:{payload.question_number}"),
    )
    try:
        answer = _ask_chatbot_with_fallback(
            message=payload.message,
            context=context,
            history=[item.model_dump() for item in payload.history],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        print(f"Student chatbot error: {exc}")
        raise HTTPException(status_code=502, detail=_friendly_ai_error_message(exc)) from exc

    return {
        "answer": answer,
        "section_type": payload.section_type,
        "question_number": payload.question_number,
    }


@app.get("/api/assignments/{code}/results")
def get_assignment_results(code: str) -> dict[str, Any]:
    try:
        return store.get_assignment_results(code)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài được giao.") from exc


@app.post("/api/assignments/{code}/regrade")
def regrade_assignment(code: str) -> dict[str, Any]:
    try:
        return store.regrade_assignment(code)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài được giao.") from exc


@app.get("/api/assignments/{code}/analytics")
def get_assignment_analytics(code: str) -> dict[str, Any]:
    try:
        return store.get_assignment_analytics(code)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài được giao.") from exc


@app.get("/api/assignments/{code}/export.csv")
def export_assignment_csv(code: str) -> Response:
    try:
        results = store.get_assignment_results(code)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài được giao.") from exc
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(_assignment_score_rows(results))
    filename = f"{code}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/assignments/{code}/export.xlsx")
def export_assignment_xlsx(code: str) -> Response:
    try:
        results = store.get_assignment_results(code)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài được giao.") from exc
    filename = f"{code}.xlsx"
    return Response(
        content=_build_xlsx(_assignment_score_rows(results)),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/exams/{draft_id}/assets/{filename}")
def get_asset(draft_id: str, filename: str) -> FileResponse:
    if Path(filename).name != filename or Path(draft_id).name != draft_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy asset.")
    asset_directory = (settings.asset_root / draft_id).resolve()
    asset_path = (asset_directory / filename).resolve()
    if not asset_path.is_relative_to(asset_directory) or not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy asset.")
    return FileResponse(asset_path)


def _draft_for_client(draft: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(draft)
    draft_id = payload["id"]
    exam = payload["exam"]

    for asset in exam.get("assets", []):
        _replace_asset_paths(asset, draft_id)
    for asset in exam.get("assets_by_id", {}).values():
        _replace_asset_paths(asset, draft_id)
    for section in exam.get("sections", []):
        for question in section.get("questions", []):
            _replace_paths_in_value(question, draft_id)
    return payload


def _assignment_for_client(assignment: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(assignment)
    draft_id = payload["draft_id"]
    exam = payload["exam"]
    for asset in exam.get("assets", []):
        _replace_asset_paths(asset, draft_id)
    for asset in exam.get("assets_by_id", {}).values():
        _replace_asset_paths(asset, draft_id)
    for section in exam.get("sections", []):
        for question in section.get("questions", []):
            _replace_paths_in_value(question, draft_id)
    payload["student_url"] = _student_assignment_url(payload["code"])
    return payload


def _student_assignment_url(code: str) -> str | None:
    if not settings.public_base_url:
        return None
    return f"{settings.public_base_url}/#student/{code}"


def _find_question(exam: dict[str, Any], section_type: str, number: int) -> dict[str, Any] | None:
    for section in exam.get("sections", []):
        if section.get("type") != section_type:
            continue
        for question in section.get("questions", []):
            if int(question.get("number", 0) or 0) == int(number):
                return question
    return None


def _find_grade_detail(grade: dict[str, Any], section_type: str, number: int) -> dict[str, Any] | None:
    for detail in grade.get("questions", []):
        if detail.get("section_type") == section_type and int(detail.get("number", 0) or 0) == int(number):
            return detail
    return None


def _build_chat_question_context(
    *,
    assignment: dict[str, Any],
    question: dict[str, Any],
    section_type: str,
    detail: dict[str, Any] | None,
    student_answer: Any,
) -> str:
    lines = [
        f"Ten bai: {assignment.get('title', '')}",
        f"Lop: {(assignment.get('classroom') or {}).get('name', '')}",
        f"Phan: {section_display(section_type)}",
        f"Cau: {question.get('number')}",
        f"Noi dung: {_markup_to_chat_text(question.get('prompt_markup') or _blocks_to_markup(question.get('prompt_blocks') or []))}",
    ]
    options_markup = question.get("options_markup") or {}
    if isinstance(options_markup, dict) and options_markup:
        lines.append("Lua chon:")
        for label in sorted(options_markup):
            lines.append(f"- {label}: {_markup_to_chat_text(options_markup[label])}")
    statements_markup = question.get("statements_markup") or {}
    if isinstance(statements_markup, dict) and statements_markup:
        lines.append("Cac y dung/sai:")
        for label in sorted(statements_markup):
            lines.append(f"- {label}: {_markup_to_chat_text(statements_markup[label])}")
    lines.extend(
        [
            f"Hoc sinh tra loi: {_answer_to_text(student_answer)}",
            f"Dap an dung: {_answer_to_text(question.get('correct_answer'))}",
        ]
    )
    if detail:
        lines.append(f"Ket qua cham: {'dung' if detail.get('correct') else 'sai'}, diem {detail.get('score')}/{detail.get('max_score')}")
        if detail.get("items"):
            lines.append(f"Chi tiet tung y: {_answer_to_text(detail.get('items'))}")
    return "\n".join(lines)


def _markup_to_chat_text(markup: Any) -> str:
    text = str(markup or "")

    def replace_math64(match: re.Match[str]) -> str:
        encoded = match.group(1)
        padding = "=" * (-len(encoded) % 4)
        try:
            decoded = base64.urlsafe_b64decode((encoded + padding).encode("ascii")).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            decoded = encoded
        return f"\\({decoded}\\)"

    text = re.sub(r"\[math64:\$([A-Za-z0-9_\-=]+)\$\]", replace_math64, text)
    text = re.sub(r"\[math:\$(.*?)\$\]", lambda match: f"\\({match.group(1)}\\)", text)
    text = re.sub(r"\[img:\$([A-Za-z0-9_-]+)\$\]", r"(anh cong thuc \1)", text)
    return " ".join(text.split())


def _answer_to_text(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if value is None or value == "":
        return "(chua tra loi)"
    return str(value)


def _replace_paths_in_value(value: Any, draft_id: str) -> None:
    if isinstance(value, dict):
        if value.get("type") == "image":
            _replace_asset_paths(value, draft_id)
        for nested in value.values():
            _replace_paths_in_value(nested, draft_id)
    elif isinstance(value, list):
        for nested in value:
            _replace_paths_in_value(nested, draft_id)


def _replace_asset_paths(asset: dict[str, Any], draft_id: str) -> None:
    for key in ("render_path", "original_path"):
        path = asset.get(key)
        if path:
            filename = Path(str(path)).name
            asset[key] = f"/api/exams/{draft_id}/assets/{filename}"


def _find_exam_asset(exam: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
    asset = exam.get("assets_by_id", {}).get(asset_id)
    if isinstance(asset, dict):
        return asset
    for candidate in exam.get("assets", []):
        if isinstance(candidate, dict) and candidate.get("asset_id") == asset_id:
            return candidate
    return None


def _asset_image_path(draft_id: str, asset: dict[str, Any]) -> Path | None:
    asset_directory = (settings.asset_root / draft_id).resolve()
    for key in ("render_path", "original_path"):
        raw_path = asset.get(key)
        if not raw_path:
            continue
        candidate = Path(str(raw_path))
        if candidate.is_absolute() and candidate.is_file() and _is_supported_ocr_image(candidate):
            return candidate
        filename = candidate.name
        if not filename:
            continue
        asset_path = (asset_directory / filename).resolve()
        if asset_path.is_relative_to(asset_directory) and asset_path.is_file() and _is_supported_ocr_image(asset_path):
            return asset_path
    return None


def _is_supported_ocr_image(path: Path) -> bool:
    return path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _configured_ocr_providers() -> tuple[str, ...]:
    providers: list[str] = []
    for provider in settings.ai_provider_chain:
        if provider == "gemini" and settings.gemini_api_keys:
            providers.append(provider)
        elif provider == "openai" and settings.openai_api_key.strip():
            providers.append(provider)
        elif provider == "openrouter" and settings.openrouter_api_key.strip():
            providers.append(provider)
        elif provider == "nvidia" and settings.nvidia_api_key.strip() and settings.nvidia_ocr_base_url:
            providers.append(provider)
    return tuple(providers)


def _configured_chat_providers() -> tuple[str, ...]:
    providers: list[str] = []
    for provider in settings.chat_provider_chain:
        if provider == "gemini" and settings.gemini_api_keys:
            providers.append(provider)
        elif provider == "openai" and settings.openai_api_key.strip():
            providers.append(provider)
        elif provider == "openrouter" and settings.openrouter_api_key.strip():
            providers.append(provider)
        elif provider == "nvidia" and settings.nvidia_api_key.strip():
            providers.append(provider)
    return tuple(providers)


def _provider_model_name(provider: str, *, kind: str) -> str:
    if provider == "gemini":
        return settings.gemini_model
    if provider == "openai":
        return settings.openai_model
    if provider == "openrouter":
        return settings.openrouter_chat_model if kind == "chat" else settings.openrouter_ocr_model
    if provider == "nvidia":
        return settings.nvidia_chat_model if kind == "chat" else settings.nvidia_ocr_model
    return ""


def _suggest_latex_for_image_with_provider(provider: str, image_path: Path) -> dict[str, Any]:
    return suggest_latex_for_image(
        image_path,
        provider,
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        gemini_api_key=settings.gemini_api_key,
        gemini_api_keys=settings.gemini_api_keys,
        gemini_model=settings.gemini_model,
        openrouter_api_key=settings.openrouter_api_key,
        openrouter_model=settings.openrouter_ocr_model,
        nvidia_api_key=settings.nvidia_api_key,
        nvidia_model=settings.nvidia_ocr_model,
        nvidia_base_url=settings.nvidia_ocr_base_url,
    )


def _suggest_latex_for_image_with_fallback(
    image_path: Path,
    providers: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    provider_chain = providers or _configured_ocr_providers()
    if not provider_chain:
        raise ValueError("Chua cau hinh provider OCR kha dung.")
    errors: list[str] = []
    for provider in provider_chain:
        try:
            suggestion = _suggest_latex_for_image_with_provider(provider, image_path)
            suggestion["provider"] = provider
            suggestion["model"] = _provider_model_name(provider, kind="ocr")
            return suggestion
        except (ValueError, FileNotFoundError, RuntimeError) as exc:
            errors.append(f"{provider}: {exc}")
    raise RuntimeError("; ".join(errors[-3:]))


def _ask_chatbot_with_provider(
    provider: str,
    *,
    message: str,
    context: str,
    history: list[dict[str, str]],
) -> str:
    return ask_chatbot(
        provider=provider,
        message=message,
        context=context,
        history=history,
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        gemini_api_key=settings.gemini_api_key,
        gemini_api_keys=settings.gemini_api_keys,
        gemini_model=settings.gemini_model,
        openrouter_api_key=settings.openrouter_api_key,
        openrouter_model=settings.openrouter_chat_model,
        nvidia_api_key=settings.nvidia_api_key,
        nvidia_model=settings.nvidia_chat_model,
    )


def _ask_chatbot_with_fallback(
    *,
    message: str,
    context: str,
    history: list[dict[str, str]],
) -> str:
    provider_chain = _configured_chat_providers()
    if not provider_chain:
        raise ValueError("Chua cau hinh provider chatbot kha dung.")
    errors: list[str] = []
    for provider in provider_chain:
        try:
            return _ask_chatbot_with_provider(
                provider,
                message=message,
                context=context,
                history=history,
            )
        except (ValueError, RuntimeError) as exc:
            errors.append(f"{provider}: {exc}")
    raise RuntimeError("; ".join(errors[-3:]))


def _auto_ocr_exam_assets(draft_id: str, exam: dict[str, Any]) -> None:
    asset_ids = _image_token_ids_in_exam(exam)
    if not asset_ids:
        return

    replacements: dict[str, str] = {}
    failures: list[str] = []

    image_items: list[tuple[str, Path]] = []
    for asset_id in asset_ids:
        asset = _find_exam_asset(exam, asset_id)
        if not asset:
            failures.append(f"{asset_id}: asset not found")
            continue
        image_path = _asset_image_path(draft_id, asset)
        if not image_path:
            failures.append(f"{asset_id}: no supported image")
            continue
        image_items.append((asset_id, image_path))

    ocr_providers = _configured_ocr_providers()
    if not ocr_providers:
        failures.extend(f"{asset_id}: no configured OCR provider" for asset_id, _ in image_items)
        worker_count = 0
    elif ocr_providers[0] == "gemini":
        def run_gemini_batch(batch: list[tuple[str, Path]]) -> None:
            batch_ids = [asset_id for asset_id, _ in batch]
            try:
                suggestions = suggest_latex_for_image_batch(
                    batch,
                    "gemini",
                    gemini_api_key=settings.gemini_api_key,
                    gemini_api_keys=settings.gemini_api_keys,
                    gemini_model=settings.gemini_model,
                )
            except (ValueError, RuntimeError) as exc:
                if len(batch) > 1 and _should_split_ocr_batch_error(exc):
                    midpoint = max(1, len(batch) // 2)
                    run_gemini_batch(batch[:midpoint])
                    run_gemini_batch(batch[midpoint:])
                else:
                    fallback_providers = ocr_providers[1:]
                    for asset_id, image_path in batch:
                        if not fallback_providers:
                            failures.append(f"{asset_id}: {exc}")
                            continue
                        try:
                            suggestion = _suggest_latex_for_image_with_fallback(image_path, fallback_providers)
                        except (ValueError, RuntimeError) as fallback_exc:
                            failures.append(f"{asset_id}: {exc}; fallback: {fallback_exc}")
                            continue
                        latex = str(suggestion.get("latex", "")).strip()
                        if latex:
                            replacements[asset_id] = math_replacement_token(latex)
                        else:
                            failures.append(f"{asset_id}: empty fallback OCR result")
                return

            image_map = {asset_id: image_path for asset_id, image_path in batch}
            for asset_id in batch_ids:
                suggestion = suggestions.get(asset_id)
                if not suggestion:
                    try:
                        suggestion = _suggest_latex_for_image_with_fallback(image_map[asset_id], ocr_providers)
                    except (ValueError, RuntimeError) as exc:
                        failures.append(f"{asset_id}: missing batch OCR result; fallback: {exc}")
                        continue
                latex = str(suggestion.get("latex", "")).strip()
                if not latex:
                    try:
                        suggestion = _suggest_latex_for_image_with_fallback(image_map[asset_id], ocr_providers)
                    except (ValueError, RuntimeError) as exc:
                        failures.append(f"{asset_id}: empty OCR result; fallback: {exc}")
                        continue
                    latex = str(suggestion.get("latex", "")).strip()
                    if not latex:
                        failures.append(f"{asset_id}: empty fallback OCR result")
                        continue
                replacements[asset_id] = math_replacement_token(latex)

        for batch in _chunks(image_items, settings.auto_ocr_batch_size):
            run_gemini_batch(batch)
        worker_count = 1
    else:
        worker_count = min(settings.auto_ocr_max_workers, len(image_items) or 1)

        def ocr_one(item: tuple[str, Path]) -> tuple[str, str | None, str | None]:
            asset_id, image_path = item
            try:
                suggestion = _suggest_latex_for_image_with_fallback(image_path, ocr_providers)
            except (ValueError, FileNotFoundError, RuntimeError) as exc:
                return asset_id, None, str(exc)

            latex = str(suggestion.get("latex", "")).strip()
            if not latex:
                return asset_id, None, "empty OCR result"
            return asset_id, math_replacement_token(latex), None

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {executor.submit(ocr_one, item): item[0] for item in image_items}
            for future in as_completed(future_map):
                asset_id, replacement, error = future.result()
                if replacement:
                    replacements[asset_id] = replacement
                if error:
                    failures.append(f"{asset_id}: {error}")

    if replacements:
        _replace_image_tokens_in_exam(exam, replacements)
    if image_items or failures:
        exam.setdefault("ocr", {})["auto_on_import"] = {
            "provider": ",".join(ocr_providers) if ocr_providers else "",
            "model": ",".join(_provider_model_name(provider, kind="ocr") for provider in ocr_providers),
            "provider_chain": ocr_providers,
            "converted_count": len(replacements),
            "failed_count": len(failures),
            "workers": worker_count,
            "batch_size": settings.auto_ocr_batch_size if ocr_providers[:1] == ("gemini",) else 1,
            "first_error": failures[0] if failures else "",
        }
    if failures:
        first_error = failures[0]
        exam.setdefault("warnings", []).append(
            {
                "code": "AUTO_OCR_PARTIAL",
                "severity": "warning",
                "message": (
                    f"Auto OCR converted {len(replacements)} assets and failed {len(failures)} assets. "
                    f"First error: {first_error}"
                ),
                "count": len(failures),
                "details": failures[:20],
            }
        )


def _clear_warnings(exam: dict[str, Any], codes: set[str]) -> None:
    warnings = exam.get("warnings")
    if not isinstance(warnings, list):
        return
    exam["warnings"] = [
        warning
        for warning in warnings
        if not isinstance(warning, dict) or warning.get("code") not in codes
    ]


def _chunks(items: list[tuple[str, Path]], size: int) -> list[list[tuple[str, Path]]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def _friendly_ai_error_message(exc: Exception) -> str:
    text = str(exc).lower()
    if any(marker in text for marker in ("api_key_invalid", "api key not valid", " 401", " 403", "permission_denied")):
        return "Trợ lý AI chưa dùng được vì API key đang sai hoặc chưa được cấu hình đúng. Giáo viên cần kiểm tra lại khóa API."
    if any(marker in text for marker in (" 429", "quota", "rate", "resource_exhausted")):
        return "Trợ lý AI đang tạm hết lượt dùng miễn phí hoặc bị giới hạn tốc độ. Em thử lại sau ít phút nhé."
    if any(marker in text for marker in ("timeout", "timed out", "khong ket noi", "unavailable", " 503")):
        return "Trợ lý AI đang khó kết nối. Em thử lại sau một lát nhé."
    return "Trợ lý AI chưa trả lời được lúc này. Giáo viên có thể kiểm tra cấu hình AI sau."


def _should_split_ocr_batch_error(exc: Exception) -> bool:
    text = str(exc).lower()
    non_splittable_markers = (
        " 401",
        " 403",
        " 429",
        "api key",
        "apikey",
        "quota",
        "rate",
        "resource_exhausted",
        "permission_denied",
        "invalid_argument",
        "not found",
        "not_found",
        "unavailable",
        " 503",
    )
    return not any(marker in text for marker in non_splittable_markers)


def _image_token_ids_in_exam(exam: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    illustration_ids = {
        str(block.get("asset_id"))
        for section in exam.get("sections", [])
        for question in section.get("questions", [])
        for blocks in (
            [question.get("prompt_blocks", [])]
            + list((question.get("options") or {}).values())
            + list((question.get("statements") or {}).values())
        )
        for block in blocks
        if block.get("type") == "image" and block.get("display_mode") == "block"
    }
    pattern = re.compile(r"\[img:\$([A-Za-z0-9_-]+)\$\]")
    for section in exam.get("sections", []):
        for question in section.get("questions", []):
            markup_values = [question.get("prompt_markup", "")]
            markup_values.extend((question.get("options_markup") or {}).values())
            markup_values.extend((question.get("statements_markup") or {}).values())
            for markup in markup_values:
                for match in pattern.finditer(str(markup)):
                    asset_id = match.group(1)
                    if asset_id not in illustration_ids and asset_id not in seen:
                        seen.add(asset_id)
                        ids.append(asset_id)
    return ids


def _replace_image_tokens_in_exam(exam: dict[str, Any], replacements: dict[str, str]) -> None:
    def replace_markup(value: Any) -> str:
        text = str(value or "")
        for asset_id, replacement in replacements.items():
            text = text.replace(f"[img:${asset_id}$]", replacement)
        return text

    for section in exam.get("sections", []):
        for question in section.get("questions", []):
            question["prompt_markup"] = replace_markup(question.get("prompt_markup"))
            if question.get("options"):
                current = question.get("options_markup") or {}
                question["options_markup"] = {
                    label: replace_markup(current.get(label))
                    for label in question["options"].keys()
                }
            if question.get("statements"):
                current = question.get("statements_markup") or {}
                question["statements_markup"] = {
                    label: replace_markup(current.get(label))
                    for label in question["statements"].keys()
                }


def _reset_exam_markup_from_blocks(exam: dict[str, Any]) -> None:
    for section in exam.get("sections", []):
        for question in section.get("questions", []):
            question["prompt_markup"] = _blocks_to_markup(question.get("prompt_blocks", []))
            if question.get("options"):
                question["options_markup"] = {
                    label: _blocks_to_markup(blocks)
                    for label, blocks in question["options"].items()
                }
            if question.get("statements"):
                question["statements_markup"] = {
                    label: _blocks_to_markup(blocks)
                    for label, blocks in question["statements"].items()
                }


def _blocks_to_markup(blocks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for block in blocks:
        if block.get("type") == "image" and block.get("asset_id"):
            parts.append(f"[img:${block['asset_id']}$]")
        elif block.get("type") == "math" and block.get("latex"):
            encoded = base64.urlsafe_b64encode(str(block["latex"]).encode("utf-8")).decode("ascii").rstrip("=")
            parts.append(f"[math64:${encoded}$]")
        else:
            parts.append(str(block.get("text", "")))
    return "".join(parts)


def _section_csv_score(section: dict[str, Any] | None) -> str:
    if not section:
        return ""
    return f"{section.get('score', 0)}/{section.get('max_score', 0)}"


def _path_is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _converter_status() -> dict[str, Any]:
    magick = _magick_status()
    magick["libreoffice"] = _libreoffice_status()
    magick["custom_font_dir"] = _custom_font_dir_status()
    return magick


def _magick_status() -> dict[str, Any]:
    binary_name = os.getenv("MAGICK_BINARY", "magick")
    binary_path = shutil.which(binary_name)
    if not binary_path:
        return {
            "available": False,
            "binary": binary_name,
            "path": None,
            "wmf": False,
            "emf": False,
        }
    try:
        version = subprocess.run(
            [binary_path, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        formats = subprocess.run(
            [binary_path, "-list", "format"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {
            "available": True,
            "binary": binary_name,
            "path": binary_path,
            "wmf": False,
            "emf": False,
            "version": "",
        }

    format_output = formats.stdout.upper()
    return {
        "available": True,
        "binary": binary_name,
        "path": binary_path,
        "wmf": "WMF" in format_output,
        "emf": "EMF" in format_output,
        "version": version.stdout.splitlines()[0] if version.stdout else "",
    }


def _libreoffice_status() -> dict[str, Any]:
    binary_path = shutil.which("soffice") or shutil.which("libreoffice")
    if not binary_path:
        return {"available": False, "path": None, "version": ""}
    try:
        version = subprocess.run(
            [binary_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"available": True, "path": binary_path, "version": ""}
    return {
        "available": True,
        "path": binary_path,
        "version": version.stdout.strip(),
    }


def _custom_font_dir_status() -> dict[str, Any]:
    font_dir = Path(os.getenv("MATH_EXAM_CUSTOM_FONT_DIR", "/usr/local/share/fonts/mathexam"))
    files: list[Path] = []
    if font_dir.exists():
        files = [
            path
            for path in font_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".ttf", ".otf", ".ttc"}
        ]
    return {
        "path": str(font_dir),
        "exists": font_dir.exists(),
        "font_count": len(files),
    }


def _assignment_score_rows(results: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = [[
        "student_code",
        "student_name",
        "status",
        "total_score",
        "max_score",
        "part_i",
        "part_ii",
        "part_iii",
        "submitted_at",
    ]]
    for submission in results["submissions"]:
        grade = submission.get("grading_detail") or {}
        by_section = grade.get("by_section", {})
        student = submission.get("student") or {}
        rows.append([
            student.get("student_code", ""),
            student.get("name", ""),
            submission.get("status", ""),
            submission.get("total_score") or "",
            submission.get("max_score") or "",
            _section_csv_score(by_section.get("single_choice")),
            _section_csv_score(by_section.get("true_false")),
            _section_csv_score(by_section.get("short_answer")),
            submission.get("submitted_at") or "",
        ])
    return rows


def _build_xlsx(rows: list[list[Any]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _xlsx_content_types())
        archive.writestr("_rels/.rels", _xlsx_root_rels())
        archive.writestr("xl/workbook.xml", _xlsx_workbook())
        archive.writestr("xl/_rels/workbook.xml.rels", _xlsx_workbook_rels())
        archive.writestr("xl/styles.xml", _xlsx_styles())
        archive.writestr("xl/worksheets/sheet1.xml", _xlsx_sheet(rows))
    return output.getvalue()


def _xlsx_sheet(rows: list[list[Any]]) -> str:
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{_xlsx_column_name(column_index)}{row_index}"
            cell_style = ' s="1"' if row_index == 1 else ""
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr"{cell_style}>'
                f"<is><t>{escape(str(value))}</t></is></c>"
            )
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="18"/>'
        '<cols>'
        '<col min="1" max="2" width="22" customWidth="1"/>'
        '<col min="3" max="9" width="16" customWidth="1"/>'
        '</cols>'
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        "</worksheet>"
    )


def _xlsx_column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xlsx_content_types() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        "</Types>"
    )


def _xlsx_root_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _xlsx_workbook() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        '<sheet name="Bang diem" sheetId="1" r:id="rId1"/>'
        "</sheets>"
        "</workbook>"
    )


def _xlsx_workbook_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )


def _xlsx_styles() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


if settings.frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
