from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def grade_exam_submission(exam: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    by_section: dict[str, dict[str, float]] = {}
    question_details: list[dict[str, Any]] = []
    total_score = 0.0
    max_score = 0.0

    for section in exam.get("sections", []):
        section_type = section.get("type")
        section_score = 0.0
        section_max = 0.0
        for question in section.get("questions", []):
            detail = _grade_question(section_type, question, answers)
            question_details.append(detail)
            section_score += detail["score"]
            section_max += detail["max_score"]
        by_section[str(section_type)] = {
            "score": _round_score(section_score),
            "max_score": _round_score(section_max),
        }
        total_score += section_score
        max_score += section_max

    return {
        "total_score": _round_score(total_score),
        "max_score": _round_score(max_score),
        "by_section": by_section,
        "questions": question_details,
    }


def _grade_question(section_type: str, question: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    number = int(question.get("number", 0))
    max_score = float(question.get("score", 0) or 0)
    expected = question.get("correct_answer")
    actual = answers.get(f"{section_type}:{number}")

    if section_type == "single_choice":
        correct = _normalize_label(actual) == _normalize_label(expected)
        score = max_score if correct else 0.0
        return _question_detail(section_type, number, actual, expected, score, max_score, correct)

    if section_type == "true_false":
        expected_items = expected if isinstance(expected, dict) else {}
        actual_items = actual if isinstance(actual, dict) else {}
        labels = sorted(expected_items.keys())
        per_item = max_score / len(labels) if labels else 0.0
        items: dict[str, dict[str, Any]] = {}
        score = 0.0
        for label in labels:
            item_correct = _normalize_label(actual_items.get(label)) == _normalize_label(expected_items.get(label))
            if item_correct:
                score += per_item
            items[label] = {
                "actual": actual_items.get(label),
                "expected": expected_items.get(label),
                "correct": item_correct,
                "score": _round_score(per_item if item_correct else 0.0),
                "max_score": _round_score(per_item),
            }
        return _question_detail(
            section_type,
            number,
            actual,
            expected,
            score,
            max_score,
            all(item["correct"] for item in items.values()) if items else False,
            {"items": items},
        )

    if section_type == "short_answer":
        correct = _normalize_short_answer(actual) == _normalize_short_answer(expected)
        score = max_score if correct else 0.0
        return _question_detail(section_type, number, actual, expected, score, max_score, correct)

    return _question_detail(section_type, number, actual, expected, 0.0, max_score, False)


def _question_detail(
    section_type: str,
    number: int,
    actual: Any,
    expected: Any,
    score: float,
    max_score: float,
    correct: bool,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    detail = {
        "section_type": section_type,
        "number": number,
        "actual": actual,
        "expected": expected,
        "score": _round_score(score),
        "max_score": _round_score(max_score),
        "correct": correct,
    }
    if extra:
        detail.update(extra)
    return detail


def _normalize_label(value: Any) -> str:
    return str(value or "").strip().upper()


def _normalize_short_answer(value: Any) -> str:
    text = " ".join(str(value or "").strip().split()).lower()
    number = _to_decimal(text)
    return str(number.normalize()) if number is not None else text


def _to_decimal(value: str) -> Decimal | None:
    normalized = value.replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _round_score(value: float) -> float:
    return round(value + 0.000000001, 4)
