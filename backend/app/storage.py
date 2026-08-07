from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.services.grading import grade_exam_submission


SCHEMA = """
CREATE TABLE IF NOT EXISTS exam_drafts (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    parsed_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS classes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    school_year TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
    id TEXT PRIMARY KEY,
    class_id TEXT NOT NULL,
    name TEXT NOT NULL,
    student_code TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (class_id) REFERENCES classes(id),
    UNIQUE (class_id, student_code)
);

CREATE TABLE IF NOT EXISTS exams (
    id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    exam_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (draft_id) REFERENCES exam_drafts(id)
);

CREATE TABLE IF NOT EXISTS exam_questions (
    id TEXT PRIMARY KEY,
    exam_id TEXT NOT NULL,
    section_type TEXT NOT NULL,
    question_number INTEGER NOT NULL,
    question_json TEXT NOT NULL,
    correct_answer_json TEXT NOT NULL,
    score REAL NOT NULL,
    FOREIGN KEY (exam_id) REFERENCES exams(id),
    UNIQUE (exam_id, section_type, question_number)
);

CREATE TABLE IF NOT EXISTS assignments (
    id TEXT PRIMARY KEY,
    exam_id TEXT NOT NULL,
    class_id TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 45,
    show_score INTEGER NOT NULL DEFAULT 0,
    show_answers INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    published_at TEXT NOT NULL,
    FOREIGN KEY (exam_id) REFERENCES exams(id),
    FOREIGN KEY (class_id) REFERENCES classes(id)
);

CREATE TABLE IF NOT EXISTS submissions (
    id TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    status TEXT NOT NULL,
    answers_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    submitted_at TEXT,
    FOREIGN KEY (assignment_id) REFERENCES assignments(id),
    FOREIGN KEY (student_id) REFERENCES students(id),
    UNIQUE (assignment_id, student_id)
);

CREATE TABLE IF NOT EXISTS submission_grades (
    id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL UNIQUE,
    total_score REAL NOT NULL,
    max_score REAL NOT NULL,
    grading_detail_json TEXT NOT NULL,
    graded_at TEXT NOT NULL,
    FOREIGN KEY (submission_id) REFERENCES submissions(id)
);

CREATE INDEX IF NOT EXISTS idx_students_class_id
ON students(class_id);

CREATE INDEX IF NOT EXISTS idx_exam_questions_exam_id
ON exam_questions(exam_id);

CREATE INDEX IF NOT EXISTS idx_assignments_code
ON assignments(code);

CREATE INDEX IF NOT EXISTS idx_submissions_assignment_student
ON submissions(assignment_id, student_id);

CREATE INDEX IF NOT EXISTS idx_submission_grades_submission_id
ON submission_grades(submission_id);
"""


class DraftStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.executescript(SCHEMA)
            self._migrate(connection)
            connection.execute("PRAGMA optimize")

    def _migrate(self, connection: sqlite3.Connection) -> None:
        assignment_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(assignments)").fetchall()
        }
        if "duration_minutes" not in assignment_columns:
            connection.execute(
                "ALTER TABLE assignments ADD COLUMN duration_minutes INTEGER NOT NULL DEFAULT 45"
            )
        if "show_score" not in assignment_columns:
            connection.execute(
                "ALTER TABLE assignments ADD COLUMN show_score INTEGER NOT NULL DEFAULT 0"
            )
        if "show_answers" not in assignment_columns:
            connection.execute(
                "ALTER TABLE assignments ADD COLUMN show_answers INTEGER NOT NULL DEFAULT 0"
            )

    def create(
        self,
        draft_id: str,
        source_filename: str,
        parsed_exam: dict[str, Any],
    ) -> dict[str, Any]:
        now = _utc_now()
        normalized = normalize_exam_for_save(parsed_exam)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO exam_drafts (
                    id, title, source_filename, parsed_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'draft', ?, ?)
                """,
                (
                    draft_id,
                    normalized.get("title") or "Đề thi chưa đặt tên",
                    source_filename,
                    json.dumps(normalized, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return self.get(draft_id)

    def get(self, draft_id: str) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT id, title, source_filename, parsed_json, status, created_at, updated_at
                FROM exam_drafts
                WHERE id = ?
                """,
                (draft_id,),
            ).fetchone()
        if row is None:
            raise KeyError(draft_id)
        return _row_to_draft(row)

    def update(self, draft_id: str, parsed_exam: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_exam_for_save(parsed_exam)
        updated_at = _utc_now()
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE exam_drafts
                SET title = ?, parsed_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    normalized.get("title") or "Đề thi chưa đặt tên",
                    json.dumps(normalized, ensure_ascii=False),
                    updated_at,
                    draft_id,
                ),
            )
        if cursor.rowcount == 0:
            raise KeyError(draft_id)
        return self.get(draft_id)

    def list_drafts(self, limit: int = 12) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, title, source_filename, parsed_json, status, created_at, updated_at
                FROM exam_drafts
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        drafts = []
        for row in rows:
            draft = _row_to_draft(row)
            exam = draft["exam"]
            drafts.append(
                {
                    "id": draft["id"],
                    "title": draft["title"],
                    "source_filename": draft["source_filename"],
                    "status": draft["status"],
                    "created_at": draft["created_at"],
                    "updated_at": draft["updated_at"],
                    "question_count": sum(len(section.get("questions", [])) for section in exam.get("sections", [])),
                    "warning_count": len(exam.get("warnings", [])),
                }
            )
        return drafts

    def list_assignments(self, limit: int = 12) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    a.id, a.code, a.status, a.duration_minutes, a.show_score, a.show_answers, a.published_at,
                    e.title, e.draft_id,
                    c.name AS class_name,
                    COUNT(DISTINCT s.id) AS student_count,
                    COUNT(DISTINCT CASE WHEN sub.status = 'submitted' THEN sub.id END) AS submitted_count,
                    AVG(g.total_score) AS average_score,
                    MAX(g.max_score) AS max_score
                FROM assignments a
                JOIN exams e ON e.id = a.exam_id
                JOIN classes c ON c.id = a.class_id
                LEFT JOIN students s ON s.class_id = c.id
                LEFT JOIN submissions sub ON sub.assignment_id = a.id AND sub.student_id = s.id
                LEFT JOIN submission_grades g ON g.submission_id = sub.id
                GROUP BY a.id
                ORDER BY a.published_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "code": row["code"],
                "status": row["status"],
                "duration_minutes": row["duration_minutes"],
                "show_score": bool(row["show_score"]),
                "show_answers": bool(row["show_answers"]),
                "published_at": row["published_at"],
                "title": row["title"],
                "draft_id": row["draft_id"],
                "class_name": row["class_name"],
                "student_count": row["student_count"],
                "submitted_count": row["submitted_count"],
                "average_score": round(row["average_score"], 2) if row["average_score"] is not None else None,
                "max_score": row["max_score"],
            }
            for row in rows
        ]

    def list_classes(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            class_rows = connection.execute(
                """
                SELECT id, name, school_year, created_at
                FROM classes
                ORDER BY created_at DESC, name
                """
            ).fetchall()
            student_rows = connection.execute(
                """
                SELECT id, class_id, name, student_code, created_at
                FROM students
                ORDER BY class_id, student_code
                """
            ).fetchall()
        students_by_class: dict[str, list[dict[str, Any]]] = {}
        for row in student_rows:
            students_by_class.setdefault(row["class_id"], []).append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "student_code": row["student_code"],
                    "created_at": row["created_at"],
                }
            )
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "school_year": row["school_year"],
                "created_at": row["created_at"],
                "students": students_by_class.get(row["id"], []),
            }
            for row in class_rows
        ]

    def upsert_class(
        self,
        class_id: str | None,
        name: str,
        school_year: str,
        students: list[dict[str, str]],
    ) -> dict[str, Any]:
        cleaned_name = name.strip()
        cleaned_school_year = school_year.strip() or "2026-2027"
        if not cleaned_name:
            raise ValueError("Tên lớp không được để trống.")
        normalized_students = _normalize_students(students)
        if not normalized_students:
            raise ValueError("Lớp cần ít nhất một học sinh.")
        now = _utc_now()
        target_class_id = class_id or uuid4().hex
        with closing(self._connect()) as connection, connection:
            if class_id:
                cursor = connection.execute(
                    """
                    UPDATE classes
                    SET name = ?, school_year = ?
                    WHERE id = ?
                    """,
                    (cleaned_name, cleaned_school_year, target_class_id),
                )
                if cursor.rowcount == 0:
                    raise KeyError(class_id)
                connection.execute("DELETE FROM students WHERE class_id = ?", (target_class_id,))
            else:
                connection.execute(
                    """
                    INSERT INTO classes (id, name, school_year, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (target_class_id, cleaned_name, cleaned_school_year, now),
                )
            connection.executemany(
                """
                INSERT INTO students (id, class_id, name, student_code, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (uuid4().hex, target_class_id, student["name"], student["student_code"], now)
                    for student in normalized_students
                ],
            )
        return self.get_class(target_class_id)

    def get_class(self, class_id: str) -> dict[str, Any]:
        for classroom in self.list_classes():
            if classroom["id"] == class_id:
                return classroom
        raise KeyError(class_id)

    def publish_assignment(
        self,
        draft_id: str,
        class_id: str,
        duration_minutes: int,
        show_score: bool = False,
        show_answers: bool = False,
    ) -> dict[str, Any]:
        draft = self.get(draft_id)
        exam = normalize_exam_for_save(draft["exam"])
        now = _utc_now()
        classroom = self.get_class(class_id)
        if not classroom["students"]:
            raise ValueError("Lớp cần ít nhất một học sinh trước khi giao đề.")
        safe_duration = max(1, min(int(duration_minutes), 300))
        exam_id = uuid4().hex
        assignment_id = uuid4().hex
        code = self._new_assignment_code()

        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO exams (id, draft_id, title, status, exam_json, created_at, updated_at)
                VALUES (?, ?, ?, 'published', ?, ?, ?)
                """,
                (
                    exam_id,
                    draft_id,
                    exam.get("title") or draft["title"],
                    json.dumps(exam, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            question_rows = []
            for section in exam.get("sections", []):
                for question in section.get("questions", []):
                    question_rows.append(
                        (
                            uuid4().hex,
                            exam_id,
                            section.get("type"),
                            int(question.get("number", 0)),
                            json.dumps(question, ensure_ascii=False),
                            json.dumps(question.get("correct_answer"), ensure_ascii=False),
                            float(question.get("score", 0)),
                        )
                    )
            connection.executemany(
                """
                INSERT INTO exam_questions (
                    id, exam_id, section_type, question_number, question_json, correct_answer_json, score
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                question_rows,
            )
            connection.execute(
                """
                INSERT INTO assignments (
                    id, exam_id, class_id, code, status, duration_minutes,
                    show_score, show_answers, created_at, published_at
                ) VALUES (?, ?, ?, ?, 'published', ?, ?, ?, ?, ?)
                """,
                (
                    assignment_id,
                    exam_id,
                    class_id,
                    code,
                    safe_duration,
                    int(show_score),
                    int(show_answers),
                    now,
                    now,
                ),
            )
        return self.get_assignment_by_code(code, include_answers=True)

    def publish_demo_assignment(self, draft_id: str) -> dict[str, Any]:
        classes = self.list_classes()
        classroom = classes[0] if classes else self.upsert_class(
            None,
            "12A1",
            "2026-2027",
            [
                {"name": "Nguyễn An", "student_code": "HS001"},
                {"name": "Trần Bình", "student_code": "HS002"},
                {"name": "Lê Chi", "student_code": "HS003"},
            ],
        )
        return self.publish_assignment(draft_id, classroom["id"], 45)

    def get_assignment_by_code(
        self,
        code: str,
        include_answers: bool = False,
        student_id: str | None = None,
    ) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            assignment = connection.execute(
                """
                SELECT
                    a.id, a.code, a.status, a.duration_minutes, a.show_score, a.show_answers, a.published_at,
                    e.id AS exam_id, e.draft_id, e.title, e.exam_json,
                    c.id AS class_id, c.name AS class_name, c.school_year
                FROM assignments a
                JOIN exams e ON e.id = a.exam_id
                JOIN classes c ON c.id = a.class_id
                WHERE a.code = ?
                """,
                (code,),
            ).fetchone()
            if assignment is None:
                raise KeyError(code)
            student_rows = connection.execute(
                """
                SELECT s.id, s.name, s.student_code, COALESCE(sub.status, 'not_started') AS status
                FROM students s
                LEFT JOIN submissions sub
                    ON sub.student_id = s.id AND sub.assignment_id = ?
                WHERE s.class_id = ?
                ORDER BY s.student_code
                """,
                (assignment["id"], assignment["class_id"]),
            ).fetchall()
            submission = None
            if student_id:
                submission = connection.execute(
                    """
                    SELECT
                        sub.id, sub.status, sub.answers_json, sub.created_at, sub.updated_at, sub.submitted_at,
                        g.grading_detail_json
                    FROM submissions sub
                    LEFT JOIN submission_grades g ON g.submission_id = sub.id
                    WHERE sub.assignment_id = ? AND sub.student_id = ?
                    """,
                    (assignment["id"], student_id),
                ).fetchone()
        exam = json.loads(assignment["exam_json"])
        student_can_see_answers = (
            student_id
            and assignment["show_answers"]
            and submission
            and submission["status"] == "submitted"
        )
        if not include_answers and not student_can_see_answers:
            exam = exam_for_student(exam)
        payload = {
            "id": assignment["id"],
            "code": assignment["code"],
            "status": assignment["status"],
            "duration_minutes": assignment["duration_minutes"],
            "show_score": bool(assignment["show_score"]),
            "show_answers": bool(assignment["show_answers"]),
            "published_at": assignment["published_at"],
            "exam_id": assignment["exam_id"],
            "draft_id": assignment["draft_id"],
            "title": assignment["title"],
            "classroom": {
                "id": assignment["class_id"],
                "name": assignment["class_name"],
                "school_year": assignment["school_year"],
            },
            "students": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "student_code": row["student_code"],
                    "status": row["status"],
                }
                for row in student_rows
            ],
            "exam": exam,
        }
        if submission:
            payload["submission"] = {
                "id": submission["id"],
                "status": submission["status"],
                "answers": json.loads(submission["answers_json"]),
                "created_at": submission["created_at"],
                "updated_at": submission["updated_at"],
                "submitted_at": submission["submitted_at"],
            }
            if assignment["show_score"] and submission["grading_detail_json"]:
                payload["submission"]["grade"] = json.loads(submission["grading_detail_json"])
        return payload

    def update_assignment_visibility(
        self,
        code: str,
        show_score: bool,
        show_answers: bool,
    ) -> dict[str, Any]:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE assignments
                SET show_score = ?, show_answers = ?
                WHERE code = ?
                """,
                (int(show_score), int(show_answers), code),
            )
        if cursor.rowcount == 0:
            raise KeyError(code)
        return self.get_assignment_by_code(code, include_answers=True)

    def save_submission(
        self,
        assignment_code: str,
        student_id: str,
        answers: dict[str, Any],
        submit: bool = False,
    ) -> dict[str, Any]:
        assignment = self.get_assignment_by_code(assignment_code, include_answers=True)
        if student_id not in {student["id"] for student in assignment["students"]}:
            raise KeyError(student_id)

        now = _utc_now()
        status = "submitted" if submit else "in_progress"
        submitted_at = now if submit else None
        stored_grade: dict[str, Any] | None = None
        with closing(self._connect()) as connection, connection:
            existing = connection.execute(
                """
                SELECT id, created_at, submitted_at
                FROM submissions
                WHERE assignment_id = ? AND student_id = ?
                """,
                (assignment["id"], student_id),
            ).fetchone()
            if existing:
                submitted_at = submitted_at or existing["submitted_at"]
                connection.execute(
                    """
                    UPDATE submissions
                    SET answers_json = ?, status = ?, updated_at = ?, submitted_at = ?
                    WHERE id = ?
                    """,
                    (
                        json.dumps(answers, ensure_ascii=False),
                        status,
                        now,
                        submitted_at,
                        existing["id"],
                    ),
                )
                submission_id = existing["id"]
                created_at = existing["created_at"]
            else:
                submission_id = uuid4().hex
                created_at = now
                connection.execute(
                    """
                    INSERT INTO submissions (
                        id, assignment_id, student_id, status, answers_json, created_at, updated_at, submitted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        submission_id,
                        assignment["id"],
                        student_id,
                        status,
                        json.dumps(answers, ensure_ascii=False),
                        now,
                        now,
                        submitted_at,
                    ),
                )
        if submit:
            stored_grade = self._store_grade(submission_id, assignment["exam"], answers)
        return {
            "id": submission_id,
            "assignment_code": assignment_code,
            "student_id": student_id,
            "status": status,
            "answers": answers,
            "created_at": created_at,
            "updated_at": now,
            "submitted_at": submitted_at,
            "grade": stored_grade if submit and assignment.get("show_score") else None,
        }

    def get_assignment_results(self, code: str) -> dict[str, Any]:
        assignment = self.get_assignment_by_code(code, include_answers=True)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    sub.id, sub.student_id, sub.status, sub.answers_json, sub.created_at, sub.updated_at, sub.submitted_at,
                    g.total_score, g.max_score, g.grading_detail_json, g.graded_at
                FROM submissions sub
                LEFT JOIN submission_grades g ON g.submission_id = sub.id
                WHERE sub.assignment_id = ?
                ORDER BY sub.updated_at DESC
                """,
                (assignment["id"],),
            ).fetchall()
        rows_by_student = {row["student_id"]: row for row in rows}
        submission_results = []
        for student in assignment["students"]:
            row = rows_by_student.get(student["id"])
            if row:
                submission_results.append(_submission_row_to_result(row, student))
            else:
                submission_results.append(_empty_submission_result(assignment["id"], student))
        return {
            "assignment": {
                "id": assignment["id"],
                "code": assignment["code"],
                "title": assignment["title"],
                "duration_minutes": assignment["duration_minutes"],
                "show_score": assignment["show_score"],
                "show_answers": assignment["show_answers"],
                "classroom": assignment["classroom"],
                "student_count": len(assignment["students"]),
            },
            "submissions": submission_results,
        }

    def regrade_assignment(self, code: str) -> dict[str, Any]:
        assignment = self.get_assignment_by_code(code, include_answers=True)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, answers_json
                FROM submissions
                WHERE assignment_id = ? AND status = 'submitted'
                """,
                (assignment["id"],),
            ).fetchall()
        for row in rows:
            self._store_grade(row["id"], assignment["exam"], json.loads(row["answers_json"]))
        return self.get_assignment_results(code)

    def get_assignment_analytics(self, code: str) -> dict[str, Any]:
        results = self.get_assignment_results(code)
        return build_assignment_analytics(results)

    def _store_grade(
        self,
        submission_id: str,
        exam: dict[str, Any],
        answers: dict[str, Any],
    ) -> dict[str, Any]:
        grade = grade_exam_submission(exam, answers)
        now = _utc_now()
        with closing(self._connect()) as connection, connection:
            existing = connection.execute(
                "SELECT id FROM submission_grades WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE submission_grades
                    SET total_score = ?, max_score = ?, grading_detail_json = ?, graded_at = ?
                    WHERE id = ?
                    """,
                    (
                        grade["total_score"],
                        grade["max_score"],
                        json.dumps(grade, ensure_ascii=False),
                        now,
                        existing["id"],
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO submission_grades (
                        id, submission_id, total_score, max_score, grading_detail_json, graded_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid4().hex,
                        submission_id,
                        grade["total_score"],
                        grade["max_score"],
                        json.dumps(grade, ensure_ascii=False),
                        now,
                    ),
                )
        return grade

    def _new_assignment_code(self) -> str:
        with closing(self._connect()) as connection:
            for _ in range(10):
                code = f"AZT-{uuid4().hex[:6].upper()}"
                exists = connection.execute(
                    "SELECT 1 FROM assignments WHERE code = ?",
                    (code,),
                ).fetchone()
                if not exists:
                    return code
        return f"AZT-{uuid4().hex[:10].upper()}"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection


def normalize_exam_for_save(parsed_exam: dict[str, Any]) -> dict[str, Any]:
    exam = deepcopy(parsed_exam)
    sections = exam.get("sections")
    if not isinstance(sections, list):
        raise ValueError("Exam must contain a sections array.")

    answer_keys: dict[str, dict[str, Any]] = {
        "single_choice": {},
        "true_false": {},
        "short_answer": {},
    }
    for section in sections:
        section_type = section.get("type")
        if section_type not in answer_keys:
            raise ValueError(f"Unsupported section type: {section_type!r}.")
        questions = section.get("questions")
        if not isinstance(questions, list):
            raise ValueError(f"Section {section_type!r} must contain questions.")
        for question in questions:
            number = str(question.get("number", ""))
            if not number:
                raise ValueError("Every question must have a number.")
            score = question.get("score", 0)
            if not isinstance(score, (int, float)) or score < 0:
                raise ValueError(f"Question {number} has an invalid score.")
            answer_keys[section_type][number] = question.get("correct_answer")

    exam["answer_keys"] = answer_keys
    return exam


def add_default_scores(parsed_exam: dict[str, Any]) -> dict[str, Any]:
    defaults = {"single_choice": 0.25, "true_false": 1.0, "short_answer": 0.5}
    exam = deepcopy(parsed_exam)
    for section in exam.get("sections", []):
        default_score = defaults.get(section.get("type"), 0)
        for question in section.get("questions", []):
            question.setdefault("score", default_score)
    return exam


def exam_for_student(parsed_exam: dict[str, Any]) -> dict[str, Any]:
    exam = deepcopy(parsed_exam)
    exam.pop("answer_keys", None)
    for section in exam.get("sections", []):
        for question in section.get("questions", []):
            question.pop("correct_answer", None)
    return exam


def _normalize_students(students: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized = []
    seen_codes: set[str] = set()
    for index, student in enumerate(students, start=1):
        name = str(student.get("name", "")).strip()
        code = str(student.get("student_code", "")).strip().upper() or f"HS{index:03d}"
        if not name:
            continue
        if code in seen_codes:
            raise ValueError(f"Mã học sinh bị trùng: {code}")
        seen_codes.add(code)
        normalized.append({"name": name, "student_code": code})
    return normalized


def _submission_row_to_result(row: sqlite3.Row, student: dict[str, Any] | None) -> dict[str, Any]:
    grading_detail = json.loads(row["grading_detail_json"]) if row["grading_detail_json"] else None
    return {
        "id": row["id"],
        "student": student,
        "status": row["status"],
        "answers": json.loads(row["answers_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "submitted_at": row["submitted_at"],
        "graded_at": row["graded_at"],
        "total_score": row["total_score"],
        "max_score": row["max_score"],
        "grading_detail": grading_detail,
    }


def _empty_submission_result(assignment_id: str, student: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"{assignment_id}:{student['id']}:not-started",
        "student": student,
        "status": "not_started",
        "answers": {},
        "created_at": None,
        "updated_at": None,
        "submitted_at": None,
        "graded_at": None,
        "total_score": None,
        "max_score": None,
        "grading_detail": None,
    }


def build_assignment_analytics(results: dict[str, Any]) -> dict[str, Any]:
    submissions = results["submissions"]
    student_count = int(results.get("assignment", {}).get("student_count") or len(submissions))
    submitted = [
        submission
        for submission in submissions
        if submission["status"] == "submitted" and submission["grading_detail"]
    ]
    scores = [float(submission["total_score"] or 0) for submission in submitted]
    max_score = max((float(submission["max_score"] or 0) for submission in submitted), default=0.0)
    average = round(sum(scores) / len(scores), 2) if scores else 0.0

    question_stats: dict[tuple[str, int], dict[str, Any]] = {}
    for submission in submitted:
        for detail in submission["grading_detail"].get("questions", []):
            key = (detail["section_type"], int(detail["number"]))
            item = question_stats.setdefault(
                key,
                {
                    "section_type": detail["section_type"],
                    "number": int(detail["number"]),
                    "attempt_count": 0,
                    "correct_count": 0,
                    "wrong_count": 0,
                    "correct_rate": 0.0,
                },
            )
            item["attempt_count"] += 1
            if detail.get("correct"):
                item["correct_count"] += 1
            else:
                item["wrong_count"] += 1

    question_rows = []
    for item in question_stats.values():
        attempts = item["attempt_count"]
        item["correct_rate"] = round(item["correct_count"] / attempts, 4) if attempts else 0.0
        question_rows.append(item)
    question_rows.sort(key=lambda item: (item["section_type"], item["number"]))
    top_wrong = sorted(
        [item for item in question_rows if item["wrong_count"] > 0],
        key=lambda item: (-item["wrong_count"], item["correct_rate"], item["section_type"], item["number"]),
    )[:5]

    distribution = _score_distribution(scores, max_score)
    return {
        "assignment": results["assignment"],
        "summary": {
            "student_count": student_count,
            "submitted_count": len(submitted),
            "average_score": average,
            "max_score": max_score,
            "highest_score": max(scores) if scores else 0.0,
            "lowest_score": min(scores) if scores else 0.0,
        },
        "distribution": distribution,
        "question_stats": question_rows,
        "top_wrong_questions": top_wrong,
        "insight": _build_insight(student_count, len(submitted), average, max_score, top_wrong),
    }


def _score_distribution(scores: list[float], max_score: float) -> list[dict[str, Any]]:
    buckets = [
        ("0-<5", 0.0, 0.5),
        ("5-<6.5", 0.5, 0.65),
        ("6.5-<8", 0.65, 0.8),
        ("8-10", 0.8, 1.0000001),
    ]
    rows = []
    for label, lower_ratio, upper_ratio in buckets:
        lower = max_score * lower_ratio
        upper = max_score * upper_ratio
        count = sum(1 for score in scores if lower <= score < upper)
        rows.append({"label": label, "count": count})
    return rows


def _build_insight(
    student_count: int,
    submitted_count: int,
    average: float,
    max_score: float,
    top_wrong: list[dict[str, Any]],
) -> str:
    if submitted_count == 0:
        return "Chưa có bài nộp để phân tích."
    completion = round(submitted_count / student_count * 100) if student_count else 0
    base = f"{submitted_count}/{student_count} học sinh đã nộp ({completion}%). Điểm trung bình {average}/{max_score}."
    if not top_wrong or top_wrong[0]["wrong_count"] == 0:
        return f"{base} Chưa có câu sai nổi bật."
    hardest = top_wrong[0]
    return (
        f"{base} Câu cần xem lại nhiều nhất là {section_display(hardest['section_type'])} "
        f"câu {hardest['number']} với {hardest['wrong_count']} lượt sai."
    )


def section_display(section_type: str) -> str:
    return {
        "single_choice": "PHẦN I",
        "true_false": "PHẦN II",
        "short_answer": "PHẦN III",
    }.get(section_type, section_type)


def _row_to_draft(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "source_filename": row["source_filename"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "exam": json.loads(row["parsed_json"]),
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
