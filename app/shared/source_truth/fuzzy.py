"""Fuzzy matching helpers for source-truth reconciliation reports."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from typing import TypeAlias

from app.shared.course_wrangling import (
    LEGACY_DEPT_ALIASES,
    course_key,
    normalize_token,
    split_course_code,
)
from app.shared.fuzzy_matching import jarowinkler_similarity, seq_similarity_score
from app.shared.source_truth.io import RowT

RowsT: TypeAlias = list[RowT]
CandidateIndexT: TypeAlias = dict[str, list[RowT]]
CourseTokenIndexT: TypeAlias = dict[str, list[RowT]]

TOKEN_RX = re.compile(r"[a-z0-9]+")
TITLE_STOP_TOKENS = {
    "and",
    "for",
    "the",
    "with",
}


def title_similarity(left: str | None, right: str | None) -> float:
    """Return conservative course-title similarity using shared fuzzy logic."""
    left_text = _clean_title(left)
    right_text = _clean_title(right)
    if not left_text or not right_text:
        return 0.0
    seq_score = seq_similarity_score(left_text, right_text)
    jw_score = jarowinkler_similarity(left_text, right_text)
    left_tokens = set(TOKEN_RX.findall(left_text))
    right_tokens = set(TOKEN_RX.findall(right_text))
    token_score = (
        len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        if left_tokens and right_tokens
        else 0.0
    )
    return max(seq_score, jw_score, token_score)


def build_course_alias_candidates(
    source_courses: Iterable[RowT],
    target_courses: Iterable[RowT],
    *,
    limit: int = 3,
    threshold: float = 0.82,
) -> RowsT:
    """Return top target-course candidates for non-canonical course witnesses."""
    targets = list(target_courses)
    target_by_key = _index_by_course_key(targets)
    target_by_token = _index_courses_by_title_token(targets)
    rows: RowsT = []
    for source in source_courses:
        source_key = _row_course_key(source)
        if not source_key:
            continue
        emitted: set[str] = set()
        exact_rows = target_by_key.get(source_key, [])
        for target in exact_rows[:limit]:
            rows.append(_course_match_row(source, target, 1.0, "exact_course_key"))
            emitted.add(_row_course_key(target))
        alias_key = _alias_course_key(source)
        for target in target_by_key.get(alias_key, []):
            target_key = _row_course_key(target)
            if target_key in emitted:
                continue
            score = title_similarity(
                source.get("course_title"), target.get("course_title")
            )
            rows.append(
                _course_match_row(source, target, score, "dept_alias_same_number")
            )
            emitted.add(target_key)
        scored = _score_title_candidates(
            source, _title_candidate_pool(source, target_by_token), emitted, threshold
        )
        for target, score in scored[: max(0, limit - len(emitted))]:
            rows.append(
                _course_match_row(
                    source,
                    target,
                    score,
                    _course_recommendation(source, target, score),
                )
            )
            emitted.add(_row_course_key(target))
    return rows


def _clean_title(value: str | None) -> str:
    """Normalize a course title for fuzzy matching."""
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _row_course_key(row: RowT) -> str:
    """Return a course key from normalized columns."""
    return row.get("course_key") or course_key(
        row.get("course_dept"), row.get("course_no")
    )


def _alias_course_key(row: RowT) -> str:
    """Return alias key if a known legacy department alias exists."""
    dept = normalize_token(row.get("course_dept"))
    alias = LEGACY_DEPT_ALIASES.get(dept, dept)
    return course_key(alias, row.get("course_no"))


def _index_by_course_key(rows: Iterable[RowT]) -> CandidateIndexT:
    """Index course rows by normalized dept+number key."""
    index: CandidateIndexT = defaultdict(list)
    for row in rows:
        key = _row_course_key(row)
        if key:
            index[key].append(row)
    return dict(index)


def _index_courses_by_title_token(rows: Iterable[RowT]) -> CourseTokenIndexT:
    """Index target courses by meaningful title tokens for bounded fuzzy matching."""
    index: CourseTokenIndexT = defaultdict(list)
    for row in rows:
        for token in _title_tokens(row.get("course_title", "")):
            index[token].append(row)
    return dict(index)


def _title_candidate_pool(source: RowT, index: CourseTokenIndexT) -> RowsT:
    """Return target courses sharing at least one meaningful title token."""
    scored: dict[str, tuple[RowT, int]] = {}
    for token in _title_tokens(source.get("course_title", "")):
        for row in index.get(token, []):
            key = _row_course_key(row)
            if not key:
                continue
            _, count = scored.get(key, (row, 0))
            scored[key] = (row, count + 1)
    ranked = sorted(scored.values(), key=lambda item: item[1], reverse=True)
    return [row for row, _ in ranked[:40]]


def _title_tokens(value: str | None) -> set[str]:
    """Return title tokens useful enough to constrain fuzzy comparison."""
    return {
        token
        for token in TOKEN_RX.findall(_clean_title(value))
        if len(token) > 2 and token not in TITLE_STOP_TOKENS
    }


def _score_title_candidates(
    source: RowT,
    targets: Iterable[RowT],
    emitted: set[str],
    threshold: float,
) -> list[tuple[RowT, float]]:
    """Return title-based candidates not already emitted."""
    scored: list[tuple[RowT, float]] = []
    source_title = source.get("course_title", "")
    if not source_title:
        return scored
    for target in targets:
        if _row_course_key(target) in emitted:
            continue
        score = title_similarity(source_title, target.get("course_title", ""))
        if score >= threshold:
            scored.append((target, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def _course_recommendation(source: RowT, target: RowT, score: float) -> str:
    """Classify fuzzy course-title candidates."""
    if _close_course_code(source, target) and score >= 0.94:
        return "strong_title_and_close_code_match"
    if _close_course_code(source, target) and score >= 0.86:
        return "possible_title_and_close_code_match"
    if score >= 0.94:
        return "strong_title_match"
    if score >= 0.86:
        return "possible_title_match"
    return "weak_title_match"


def _close_course_code(source: RowT, target: RowT) -> bool:
    """Return True when course identities are close enough to prioritize review."""
    source_dept, source_no = split_course_code(_row_course_key(source))
    target_dept, target_no = split_course_code(_row_course_key(target))
    if source_dept != target_dept or not source_no or not target_no:
        return False
    if source_no == target_no:
        return True
    return source_no[-2:] == target_no[-2:]


def _course_match_row(
    source: RowT, target: RowT, score: float, recommendation: str
) -> RowT:
    """Build one course alias candidate report row."""
    return {
        "source_course_key": _row_course_key(source),
        "source_label": _course_label(source),
        "source_name": source.get("source_name", ""),
        "target_course_key": _row_course_key(target),
        "target_label": _course_label(target),
        "target_name": target.get("source_name", ""),
        "score": f"{score:.3f}",
        "recommendation": recommendation,
    }


def _course_label(row: RowT) -> str:
    """Return readable course code/title label."""
    return " ".join(
        value
        for value in (
            row.get("course_dept", ""),
            row.get("course_no", ""),
            row.get("course_title", ""),
        )
        if value
    )
