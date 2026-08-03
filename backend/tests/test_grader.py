from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.grading import grade_exam_submission


class GraderTest(unittest.TestCase):
    def test_grades_supported_question_types(self) -> None:
        exam = {
            "sections": [
                {
                    "type": "single_choice",
                    "questions": [{"number": 1, "score": 0.25, "correct_answer": "B"}],
                },
                {
                    "type": "true_false",
                    "questions": [
                        {
                            "number": 1,
                            "score": 1,
                            "correct_answer": {"a": "S", "b": "Đ", "c": "S", "d": "Đ"},
                        }
                    ],
                },
                {
                    "type": "short_answer",
                    "questions": [{"number": 1, "score": 0.5, "correct_answer": "0,88"}],
                },
            ]
        }
        result = grade_exam_submission(
            exam,
            {
                "single_choice:1": "B",
                "true_false:1": {"a": "S", "b": "S", "c": "S", "d": "Đ"},
                "short_answer:1": "0.880",
            },
        )

        self.assertEqual(1.5, result["total_score"])
        self.assertEqual(1.75, result["max_score"])
        self.assertEqual(0.75, result["by_section"]["true_false"]["score"])
        self.assertTrue(result["questions"][0]["correct"])
        self.assertFalse(result["questions"][1]["correct"])
        self.assertTrue(result["questions"][2]["correct"])


if __name__ == "__main__":
    unittest.main()
