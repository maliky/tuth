"""Student identity fuzzy matching for source-truth reconciliation reports."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import TypeAlias

from app.shared.fuzzy_matching import name_similarity, normalize_name_tokens
from app.shared.source_truth.io import RowT

RowsT: TypeAlias = list[RowT]
CandidateIndexT: TypeAlias = dict[str, list[RowT]]


def build_student_identity_candidates(
    source_students: Iterable[RowT],
    grapro_students: Iterable[RowT],
    *,
    threshold: float = 0.84,
    limit: int = 3,
) -> RowsT:
    """Return identity candidates using exact id and shared name similarity."""
    candidates = list(grapro_students)
    by_id = {
        row.get("student_id", ""): row for row in candidates if row.get("student_id")
    }
    by_surname = _index_students_by_surname(candidates)
    rows: RowsT = []
    for source in source_students:
        source_id = source.get("student_id", "")
        exact = by_id.get(source_id)
        if exact is not None:
            score = name_similarity(
                source.get("student_name", ""), exact.get("student_name", "")
            )
            rows.append(
                _student_match_row(source, exact, score or 1.0, "exact_student_id")
            )
            continue
        surname, _ = normalize_name_tokens(source.get("student_name", ""))
        pool = by_surname.get(surname, candidates if surname else [])
        scored = _score_student_candidates(source, pool, threshold)
        for target, score in scored[:limit]:
            rows.append(
                _student_match_row(source, target, score, _student_recommendation(score))
            )
    return rows


def _index_students_by_surname(rows: Iterable[RowT]) -> CandidateIndexT:
    """Index student candidates by normalized surname."""
    index: CandidateIndexT = defaultdict(list)
    for row in rows:
        surname, _ = normalize_name_tokens(row.get("student_name", ""))
        if surname:
            index[surname].append(row)
    return dict(index)


def _score_student_candidates(
    source: RowT, candidates: Iterable[RowT], threshold: float
) -> list[tuple[RowT, float]]:
    """Return name-similarity candidates above threshold."""
    scored: list[tuple[RowT, float]] = []
    source_name = source.get("student_name", "")
    if not source_name:
        return scored
    for target in candidates:
        score = name_similarity(source_name, target.get("student_name", ""))
        if score >= threshold:
            scored.append((target, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def _student_recommendation(score: float) -> str:
    """Classify fuzzy student-name candidates."""
    if score >= 0.94:
        return "strong_name_match"
    return "possible_name_match"


def _student_match_row(
    source: RowT, target: RowT, score: float, recommendation: str
) -> RowT:
    """Build one student identity candidate report row."""
    return {
        "source_student_id": source.get("student_id", ""),
        "source_student_name": source.get("student_name", ""),
        "source_name": source.get("source_name", ""),
        "target_student_id": target.get("student_id", ""),
        "target_student_name": target.get("student_name", ""),
        "target_name": target.get("source_name", ""),
        "score": f"{score:.3f}",
        "recommendation": recommendation,
    }
