"""Match current TUSIS courses to TUCurricula description sources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from app.academics.models.course import Course
from app.shared.course_wrangling import (
    LEGACY_DEPT_ALIASES,
    course_key,
    normalize_token,
    split_course_code,
)
from app.shared.source_truth.course_aliases import CourseAliasMapT
from app.shared.source_truth.fuzzy import title_similarity
from app.shared.source_truth.io import RowT, read_rows

SourceRowsByKeyT: TypeAlias = dict[str, list["DescriptionSourceT"]]

TITLE_MATCH_THRESHOLD = 0.94


@dataclass(frozen=True)
class DescriptionSourceT:
    """One org-derived course row carrying a reusable description."""

    key: str
    department: str
    number: str
    title: str
    description: str
    source_files: str


@dataclass(frozen=True)
class DescriptionCatalogT:
    """Indexed description sources for exact and bounded fuzzy lookup."""

    by_key: SourceRowsByKeyT
    by_number: SourceRowsByKeyT


@dataclass(frozen=True)
class DescriptionDecisionT:
    """Resolution result for one current course."""

    source: DescriptionSourceT | None
    action: str
    reason: str
    match_method: str = ""
    score: float = 0.0


def load_description_catalog(import_dir: Path) -> DescriptionCatalogT:
    """Load TUCurricula course descriptions from ``academic_course.tsv``."""
    by_key: SourceRowsByKeyT = {}
    by_number: SourceRowsByKeyT = {}
    for row in read_rows(import_dir / "academic_course.tsv"):
        source = _description_source(row)
        if source is None:
            continue
        by_key.setdefault(source.key, []).append(source)
        by_number.setdefault(source.number, []).append(source)
    return DescriptionCatalogT(by_key=by_key, by_number=by_number)


def resolve_description_decision(
    course: Course,
    catalog: DescriptionCatalogT,
    alias_map: CourseAliasMapT,
) -> DescriptionDecisionT:
    """Return the safest available description source for one course."""
    current_key = current_course_key(course)
    exact = _unique_sources(catalog.by_key.get(current_key, []))
    if len(exact) == 1:
        return _match_decision(exact[0], "exact_course_key", 1.0)
    if len(exact) > 1:
        return _ambiguous_decision("ambiguous exact course-key descriptions")

    alias_key = alias_map.get(current_key, "")
    if alias_key:
        alias_matches = _unique_sources(catalog.by_key.get(alias_key, []))
        if len(alias_matches) == 1:
            return _match_decision(alias_matches[0], "approved_alias", 1.0)
        if len(alias_matches) > 1:
            return _ambiguous_decision("ambiguous approved-alias descriptions")

    return _fuzzy_description_decision(course, catalog)


def current_course_key(course: Course) -> str:
    """Return the current course identity key."""
    return course_key(course.department.code, course.number)


def no_match_decision(reason: str) -> DescriptionDecisionT:
    """Return a no-match decision."""
    return DescriptionDecisionT(source=None, action="skipped_no_match", reason=reason)


def _fuzzy_description_decision(
    course: Course,
    catalog: DescriptionCatalogT,
) -> DescriptionDecisionT:
    """Find a conservative same-number/title match for legacy course codes."""
    current_dept = normalize_token(course.department.code)
    current_number = normalize_token(course.number)
    current_title = course.title or ""
    if not current_number or not current_title:
        return no_match_decision("missing current number or title")

    scored: list[tuple[DescriptionSourceT, float]] = []
    for source in catalog.by_number.get(current_number, []):
        if not _close_department(current_dept, source.department):
            continue
        score = title_similarity(current_title, source.title)
        if score >= TITLE_MATCH_THRESHOLD:
            scored.append((source, score))
    if not scored:
        return no_match_decision("no safe description match")

    scored.sort(key=lambda item: (-item[1], item[0].key))
    best_source, best_score = scored[0]
    top_matches = [source for source, score in scored if abs(best_score - score) < 0.001]
    if len({source.key for source in top_matches}) > 1:
        return _ambiguous_decision("multiple same-score fuzzy matches")
    return _match_decision(best_source, "same_number_close_dept_title", best_score)


def _description_source(row: RowT) -> DescriptionSourceT | None:
    """Return a description source from one TSV row, or None when unusable."""
    description = (row.get("description") or "").strip()
    if not description:
        return None
    department = normalize_token(row.get("course_dept"))
    number = normalize_token(row.get("course_no"))
    if not department or not number:
        department, number = split_course_code(row.get("source_course_key"))
    key = course_key(department, number)
    if not key:
        return None
    return DescriptionSourceT(
        key=key,
        department=department,
        number=number,
        title=(row.get("course_title") or "").strip(),
        description=description,
        source_files=(row.get("source_files") or row.get("source_path") or "").strip(),
    )


def _unique_sources(sources: list[DescriptionSourceT]) -> list[DescriptionSourceT]:
    """Collapse duplicate TSV witnesses with identical description content."""
    unique: dict[tuple[str, str], DescriptionSourceT] = {}
    for source in sources:
        unique.setdefault((source.title, source.description), source)
    return list(unique.values())


def _close_department(current_dept: str, source_dept: str) -> bool:
    """Return True for approved or shape-close department-code variants."""
    if current_dept == source_dept:
        return True
    if LEGACY_DEPT_ALIASES.get(current_dept) == source_dept:
        return True
    if LEGACY_DEPT_ALIASES.get(source_dept) == current_dept:
        return True
    min_len = min(len(current_dept), len(source_dept))
    if min_len < 3:
        return False
    return current_dept.startswith(source_dept) or source_dept.startswith(current_dept)


def _match_decision(
    source: DescriptionSourceT,
    match_method: str,
    score: float,
) -> DescriptionDecisionT:
    """Return a successful source-description decision."""
    return DescriptionDecisionT(
        source=source,
        action="matched",
        reason="description source found",
        match_method=match_method,
        score=score,
    )


def _ambiguous_decision(reason: str) -> DescriptionDecisionT:
    """Return an ambiguity decision."""
    return DescriptionDecisionT(source=None, action="skipped_ambiguous", reason=reason)


__all__ = [
    "DescriptionCatalogT",
    "DescriptionDecisionT",
    "DescriptionSourceT",
    "current_course_key",
    "load_description_catalog",
    "no_match_decision",
    "resolve_description_decision",
]
