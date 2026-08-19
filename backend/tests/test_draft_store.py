from __future__ import annotations

import sys
import sqlite3
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.storage import DraftStore, add_default_scores


class DraftStoreTest(unittest.TestCase):
    @staticmethod
    def _create_assignment(store: DraftStore, *, max_attempts: int = 1) -> dict:
        exam = add_default_scores(
            {
                "title": "Đề kiểm tra lượt làm",
                "sections": [
                    {
                        "type": "single_choice",
                        "questions": [{"number": 1, "prompt_blocks": [], "correct_answer": "A"}],
                    },
                    {"type": "true_false", "questions": []},
                    {"type": "short_answer", "questions": []},
                ],
                "answer_keys": {},
                "assets": [],
                "warnings": [],
            }
        )
        store.create("attempt-draft", "attempt.docx", exam)
        classroom = store.upsert_class(
            None,
            "12A1",
            "2026-2027",
            [
                {"name": "Nguyễn An", "student_code": "HS001"},
                {"name": "Trần Bình", "student_code": "HS002"},
            ],
        )
        return store.publish_assignment(
            "attempt-draft",
            classroom["id"],
            45,
            max_attempts=max_attempts,
        )

    def test_create_and_update_keeps_answer_keys_in_sync(self) -> None:
        exam = add_default_scores(
            {
                "title": "Đề kiểm tra",
                "sections": [
                    {
                        "type": "single_choice",
                        "questions": [
                            {"number": 1, "prompt_blocks": [], "correct_answer": "B"}
                        ],
                    },
                    {"type": "true_false", "questions": []},
                    {"type": "short_answer", "questions": []},
                ],
                "answer_keys": {},
                "assets": [],
                "warnings": [],
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            store = DraftStore(Path(tmp) / "test.sqlite3")
            store.initialize()
            created = store.create("draft-1", "sample.docx", exam)
            created["exam"]["sections"][0]["questions"][0]["correct_answer"] = "D"
            created["exam"]["sections"][0]["questions"][0]["score"] = 0.5
            updated = store.update("draft-1", created["exam"])

        self.assertEqual("D", updated["exam"]["answer_keys"]["single_choice"]["1"])
        self.assertEqual(0.5, updated["exam"]["sections"][0]["questions"][0]["score"])

    def test_negative_score_is_rejected(self) -> None:
        exam = {
            "title": "Invalid",
            "sections": [
                {
                    "type": "short_answer",
                    "questions": [{"number": 1, "score": -1, "correct_answer": "1"}],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            store = DraftStore(Path(tmp) / "test.sqlite3")
            store.initialize()
            with self.assertRaises(ValueError):
                store.create("draft-2", "sample.docx", exam)

    def test_publish_demo_assignment_persists_runner_entities(self) -> None:
        exam = add_default_scores(
            {
                "title": "Đề giữa kỳ",
                "sections": [
                    {
                        "type": "single_choice",
                        "questions": [
                            {"number": 1, "prompt_blocks": [], "correct_answer": "B"}
                        ],
                    },
                    {
                        "type": "true_false",
                        "questions": [
                            {
                                "number": 1,
                                "prompt_blocks": [],
                                "statements": {},
                                "correct_answer": {"a": "S", "b": "Đ"},
                            }
                        ],
                    },
                    {
                        "type": "short_answer",
                        "questions": [
                            {"number": 1, "prompt_blocks": [], "correct_answer": "63"}
                        ],
                    },
                ],
                "answer_keys": {},
                "assets": [],
                "warnings": [],
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            store = DraftStore(Path(tmp) / "test.sqlite3")
            store.initialize()
            store.create("draft-3", "sample.docx", exam)
            classroom = store.upsert_class(
                None,
                "12A2",
                "2026-2027",
                [
                    {"name": "Nguyễn An", "student_code": "HS001"},
                    {"name": "Trần Bình", "student_code": "HS002"},
                    {"name": "Lê Chi", "student_code": "HS003"},
                ],
            )
            assignment = store.publish_assignment("draft-3", classroom["id"], 60)
            student_assignment = store.get_assignment_by_code(assignment["code"])
            submission = store.save_submission(
                assignment["code"],
                assignment["students"][0]["id"],
                {"single_choice:1": "B", "true_false:1": {"a": "S", "b": "Đ"}, "short_answer:1": "63"},
                submit=True,
            )
            stored_assignment = store.get_assignment_by_code(
                assignment["code"],
                student_id=assignment["students"][0]["id"],
            )
            draft_summaries = store.list_drafts()
            assignment_summaries = store.list_assignments()
            results = store.get_assignment_results(assignment["code"])
            regraded = store.regrade_assignment(assignment["code"])
            analytics = store.get_assignment_analytics(assignment["code"])
            visible_assignment = store.update_assignment_visibility(assignment["code"], True, False)
            visible_student_assignment = store.get_assignment_by_code(
                assignment["code"],
                student_id=assignment["students"][0]["id"],
            )

        self.assertEqual("12A2", assignment["classroom"]["name"])
        self.assertEqual(60, assignment["duration_minutes"])
        self.assertFalse(assignment["show_score"])
        self.assertFalse(assignment["show_answers"])
        self.assertEqual(3, len(assignment["students"]))
        self.assertEqual("submitted", submission["status"])
        self.assertIn("created_at", submission)
        self.assertIn("updated_at", submission)
        self.assertEqual("submitted", stored_assignment["submission"]["status"])
        self.assertIn("created_at", stored_assignment["submission"])
        self.assertEqual("B", stored_assignment["submission"]["answers"]["single_choice:1"])
        self.assertEqual(1, len(draft_summaries))
        self.assertEqual(1, len(assignment_summaries))
        self.assertEqual(3, assignment_summaries[0]["student_count"])
        self.assertEqual(1, assignment_summaries[0]["submitted_count"])
        self.assertEqual(60, assignment_summaries[0]["duration_minutes"])
        self.assertIsNone(submission["grade"])
        self.assertTrue(visible_assignment["show_score"])
        self.assertFalse(visible_assignment["show_answers"])
        self.assertEqual(1.75, visible_student_assignment["submission"]["grade"]["total_score"])
        self.assertEqual(3, len(results["submissions"]))
        self.assertEqual(2, sum(1 for item in results["submissions"] if item["status"] == "not_started"))
        self.assertEqual(1.75, regraded["submissions"][0]["total_score"])
        self.assertEqual(1, analytics["summary"]["submitted_count"])
        self.assertEqual(1.75, analytics["summary"]["average_score"])
        self.assertEqual(4, len(analytics["distribution"]))
        self.assertIn("Điểm trung bình", analytics["insight"])
        self.assertNotIn("answer_keys", student_assignment["exam"])
        self.assertNotIn(
            "correct_answer",
            student_assignment["exam"]["sections"][0]["questions"][0],
        )

    def test_sync_published_exams_for_draft_updates_assignment_exam(self) -> None:
        exam = add_default_scores(
            {
                "title": "OCR sync",
                "sections": [
                    {
                        "type": "single_choice",
                        "questions": [
                            {
                                "number": 1,
                                "prompt_blocks": [],
                                "prompt_markup": "Tinh [img:$img_0001$]",
                                "options_markup": {},
                                "correct_answer": "A",
                            }
                        ],
                    },
                    {"type": "true_false", "questions": []},
                    {"type": "short_answer", "questions": []},
                ],
                "answer_keys": {},
                "assets": [],
                "warnings": [],
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            store = DraftStore(Path(tmp) / "test.sqlite3")
            store.initialize()
            store.create("draft-sync", "sample.docx", exam)
            classroom = store.upsert_class(
                None,
                "12A3",
                "2026-2027",
                [{"name": "Minh Duc", "student_code": "HS001"}],
            )
            assignment = store.publish_assignment("draft-sync", classroom["id"], 45)

            updated_exam = store.get("draft-sync")["exam"]
            updated_exam["sections"][0]["questions"][0]["prompt_markup"] = "Tinh [math64:$eCsx$]"
            synced_count = store.sync_published_exams_for_draft("draft-sync", updated_exam)
            synced_assignment = store.get_assignment_by_code(assignment["code"])

        synced_question = synced_assignment["exam"]["sections"][0]["questions"][0]
        self.assertEqual(1, synced_count)
        self.assertIn("[math64:$eCsx$]", synced_question["prompt_markup"])
        self.assertNotIn("[img:$img_0001$]", synced_question["prompt_markup"])

    def test_multiple_attempts_resume_limit_and_teacher_grant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DraftStore(Path(tmp) / "test.sqlite3")
            store.initialize()
            assignment = self._create_assignment(store, max_attempts=2)
            student_id = assignment["students"][0]["id"]

            first = store.start_submission_attempt(assignment["code"], student_id)
            resumed = store.start_submission_attempt(assignment["code"], student_id)
            store.save_submission(assignment["code"], student_id, {"single_choice:1": "B"}, submit=True)
            second = store.start_submission_attempt(assignment["code"], student_id)
            store.save_submission(assignment["code"], student_id, {"single_choice:1": "A"}, submit=True)

            with self.assertRaises(ValueError):
                store.start_submission_attempt(assignment["code"], student_id)

            granted_results = store.grant_extra_attempt(assignment["code"], student_id)
            third = store.start_submission_attempt(assignment["code"], student_id)
            results = store.get_assignment_results(assignment["code"])

        student_result = next(item for item in results["submissions"] if item["student"]["id"] == student_id)
        granted_student = next(item for item in granted_results["submissions"] if item["student"]["id"] == student_id)
        self.assertEqual(first["id"], resumed["id"])
        self.assertEqual(1, first["attempt_no"])
        self.assertEqual(2, second["attempt_no"])
        self.assertEqual(3, third["attempt_no"])
        self.assertEqual(3, granted_student["attempt_limit"])
        self.assertEqual(3, student_result["attempt_count"])
        self.assertEqual(2, student_result["attempt_no"])
        self.assertEqual(0.25, student_result["total_score"])

    def test_roster_sync_preserves_students_and_submission_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DraftStore(Path(tmp) / "test.sqlite3")
            store.initialize()
            assignment = self._create_assignment(store)
            original_students = {student["student_code"]: student for student in assignment["students"]}
            store.save_submission(
                assignment["code"],
                original_students["HS001"]["id"],
                {"single_choice:1": "A"},
                submit=True,
            )

            updated_class = store.upsert_class(
                assignment["classroom"]["id"],
                "12A1",
                "2026-2027",
                [
                    {"name": "Nguyễn An Đã Sửa", "student_code": "HS001"},
                    {"name": "Lê Chi", "student_code": "HS003"},
                ],
            )
            synced_assignment = store.sync_assignment_students(assignment["code"])
            results = store.get_assignment_results(assignment["code"])

        updated_students = {student["student_code"]: student for student in updated_class["students"]}
        assigned_codes = {student["student_code"] for student in synced_assignment["students"]}
        archived = next(item for item in results["submissions"] if item["student"]["student_code"] == "HS002")
        retained = next(item for item in results["submissions"] if item["student"]["student_code"] == "HS001")
        self.assertEqual(original_students["HS001"]["id"], updated_students["HS001"]["id"])
        self.assertEqual("Nguyễn An Đã Sửa", retained["student"]["name"])
        self.assertEqual({"HS001", "HS003"}, assigned_codes)
        self.assertFalse(archived["active"])
        self.assertEqual("submitted", retained["status"])
        self.assertEqual(1, retained["attempt_count"])

    def test_migration_keeps_existing_submission_as_attempt_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database_path = Path(tmp) / "legacy.sqlite3"
            connection = sqlite3.connect(database_path)
            connection.executescript(
                """
                CREATE TABLE classes (id TEXT PRIMARY KEY, name TEXT, school_year TEXT, created_at TEXT);
                CREATE TABLE students (
                    id TEXT PRIMARY KEY, class_id TEXT, name TEXT, student_code TEXT, created_at TEXT,
                    UNIQUE (class_id, student_code)
                );
                CREATE TABLE assignments (
                    id TEXT PRIMARY KEY, exam_id TEXT, class_id TEXT, code TEXT UNIQUE, status TEXT,
                    duration_minutes INTEGER, show_score INTEGER, show_answers INTEGER,
                    created_at TEXT, published_at TEXT
                );
                CREATE TABLE submissions (
                    id TEXT PRIMARY KEY, assignment_id TEXT, student_id TEXT, status TEXT,
                    answers_json TEXT, created_at TEXT, updated_at TEXT, submitted_at TEXT,
                    UNIQUE (assignment_id, student_id)
                );
                INSERT INTO classes VALUES ('class-1', '12A1', '2026-2027', '2026-01-01');
                INSERT INTO students VALUES ('student-1', 'class-1', 'Nguyễn An', 'HS001', '2026-01-01');
                INSERT INTO assignments VALUES (
                    'assignment-1', 'exam-1', 'class-1', 'OLD-CODE', 'published', 45, 0, 0,
                    '2026-01-01', '2026-01-01'
                );
                INSERT INTO submissions VALUES (
                    'submission-1', 'assignment-1', 'student-1', 'submitted', '{}',
                    '2026-01-01', '2026-01-01', '2026-01-01'
                );
                """
            )
            connection.close()

            store = DraftStore(database_path)
            store.initialize()
            connection = sqlite3.connect(database_path)
            attempt_no = connection.execute(
                "SELECT attempt_no FROM submissions WHERE id = 'submission-1'"
            ).fetchone()[0]
            membership = connection.execute(
                "SELECT active FROM assignment_students WHERE assignment_id = 'assignment-1' AND student_id = 'student-1'"
            ).fetchone()
            assignment_settings = connection.execute(
                "SELECT max_attempts, score_policy FROM assignments WHERE id = 'assignment-1'"
            ).fetchone()
            connection.close()

        self.assertEqual(1, attempt_no)
        self.assertEqual((1,), membership)
        self.assertEqual((1, "highest"), assignment_settings)


if __name__ == "__main__":
    unittest.main()
