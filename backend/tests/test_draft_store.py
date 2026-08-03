from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.storage import DraftStore, add_default_scores


class DraftStoreTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
