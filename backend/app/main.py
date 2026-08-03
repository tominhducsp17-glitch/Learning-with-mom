from __future__ import annotations

import csv
import io
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.app.config import get_settings
from backend.app.services.parser import parse_docx_exam
from backend.app.storage import DraftStore, add_default_scores


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


@app.on_event("startup")
def initialize_storage() -> None:
    settings.upload_root.mkdir(parents=True, exist_ok=True)
    settings.asset_root.mkdir(parents=True, exist_ok=True)
    store.initialize()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}


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
    writer.writerow([
        "student_code",
        "student_name",
        "status",
        "total_score",
        "max_score",
        "part_i",
        "part_ii",
        "part_iii",
        "submitted_at",
    ])
    for submission in results["submissions"]:
        grade = submission.get("grading_detail") or {}
        by_section = grade.get("by_section", {})
        student = submission.get("student") or {}
        writer.writerow([
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
    filename = f"{code}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
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
    for section in exam.get("sections", []):
        for question in section.get("questions", []):
            _replace_paths_in_value(question, draft_id)
    return payload


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


def _section_csv_score(section: dict[str, Any] | None) -> str:
    if not section:
        return ""
    return f"{section.get('score', 0)}/{section.get('max_score', 0)}"


if settings.frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
