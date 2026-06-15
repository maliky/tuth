"""Backfill blank TUSIS course descriptions from TUCurricula imports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from django.db import transaction

from app.academics.course_description_matching import (
    DescriptionCatalogT,
    DescriptionDecisionT,
    DescriptionSourceT,
    current_course_key,
    load_description_catalog,
    no_match_decision,
    resolve_description_decision,
)
from app.academics.models.course import Course
from app.shared.source_truth.course_aliases import (
    DEFAULT_APPROVED_ALIAS_PATH,
    CourseAliasMapT,
    load_approved_course_aliases,
)
from app.shared.source_truth.io import RowT, write_tsv

CounterMapT: TypeAlias = dict[str, int]

REPORT_HEADERS = (
    "course_id",
    "course_key",
    "course_code",
    "course_title",
    "current_description_len",
    "action",
    "reason",
    "source_course_key",
    "source_course_title",
    "match_method",
    "score",
    "new_description_len",
    "source_files",
)


@dataclass(frozen=True)
class BackfillSummaryT:
    """Summary of one course-description backfill pass."""

    considered: int
    updated: int
    would_update: int
    skipped_existing: int
    skipped_no_match: int
    skipped_ambiguous: int
    report_path: Path | None


def backfill_course_descriptions(
    *,
    import_dir: Path,
    report_path: Path | None = None,
    approved_aliases_path: Path = DEFAULT_APPROVED_ALIAS_PATH,
    apply: bool = False,
    overwrite_existing: bool = False,
) -> BackfillSummaryT:
    """Backfill current Course descriptions from org-derived TSV data."""
    catalog = load_description_catalog(import_dir)
    alias_map, _ = load_approved_course_aliases(approved_aliases_path)
    counters = _empty_counters()
    report_rows: list[RowT] = []

    if apply:
        with transaction.atomic():
            _run_backfill(
                catalog=catalog,
                alias_map=alias_map,
                counters=counters,
                report_rows=report_rows,
                apply=True,
                overwrite_existing=overwrite_existing,
            )
    else:
        _run_backfill(
            catalog=catalog,
            alias_map=alias_map,
            counters=counters,
            report_rows=report_rows,
            apply=False,
            overwrite_existing=overwrite_existing,
        )

    if report_path is not None:
        write_tsv(report_path, REPORT_HEADERS, report_rows)

    return BackfillSummaryT(
        considered=counters["considered"],
        updated=counters["updated"],
        would_update=counters["would_update"],
        skipped_existing=counters["skipped_existing"],
        skipped_no_match=counters["skipped_no_match"],
        skipped_ambiguous=counters["skipped_ambiguous"],
        report_path=report_path,
    )


def _run_backfill(
    *,
    catalog: DescriptionCatalogT,
    alias_map: CourseAliasMapT,
    counters: CounterMapT,
    report_rows: list[RowT],
    apply: bool,
    overwrite_existing: bool,
) -> None:
    """Evaluate current courses and optionally persist safe description updates."""
    courses = Course.objects.select_related("department").order_by(
        "department__code", "number", "id"
    )
    for course in courses.iterator():
        counters["considered"] += 1
        decision = _course_decision(
            course=course,
            catalog=catalog,
            alias_map=alias_map,
            apply=apply,
            overwrite_existing=overwrite_existing,
        )
        counters[_counter_key(decision.action)] += 1
        report_rows.append(_report_row(course, decision))


def _course_decision(
    *,
    course: Course,
    catalog: DescriptionCatalogT,
    alias_map: CourseAliasMapT,
    apply: bool,
    overwrite_existing: bool,
) -> DescriptionDecisionT:
    """Return and optionally persist the description decision for one course."""
    if _has_description(course) and not overwrite_existing:
        return DescriptionDecisionT(
            source=None,
            action="skipped_existing_description",
            reason="description already present",
        )
    decision = resolve_description_decision(course, catalog, alias_map)
    if decision.source is None:
        return decision
    return _persist_or_mark(course, decision, apply)


def _persist_or_mark(
    course: Course,
    decision: DescriptionDecisionT,
    apply: bool,
) -> DescriptionDecisionT:
    """Persist the source description or mark the row as dry-run updateable."""
    source = decision.source
    if source is None:
        return no_match_decision("missing source after match decision")
    if apply:
        course.description = source.description
        course.save(update_fields=["description"])
        return _applied_decision(source, decision)
    return DescriptionDecisionT(
        source=source,
        action="would_update",
        reason="dry-run description match",
        match_method=decision.match_method,
        score=decision.score,
    )


def _applied_decision(
    source: DescriptionSourceT,
    decision: DescriptionDecisionT,
) -> DescriptionDecisionT:
    """Return a persisted update decision preserving match provenance."""
    return DescriptionDecisionT(
        source=source,
        action="updated",
        reason="description copied from TUCurricula source",
        match_method=decision.match_method,
        score=decision.score,
    )


def _report_row(course: Course, decision: DescriptionDecisionT) -> RowT:
    """Build one audit TSV row."""
    source = decision.source
    return {
        "course_id": str(course.id),
        "course_key": current_course_key(course),
        "course_code": course.short_code or course.code or "",
        "course_title": course.title or "",
        "current_description_len": str(len(course.description or "")),
        "action": decision.action,
        "reason": decision.reason,
        "source_course_key": source.key if source else "",
        "source_course_title": source.title if source else "",
        "match_method": decision.match_method,
        "score": f"{decision.score:.3f}" if decision.score else "",
        "new_description_len": str(len(source.description)) if source else "",
        "source_files": source.source_files if source else "",
    }


def _has_description(course: Course) -> bool:
    """Return True when a current course already has meaningful description."""
    return bool((course.description or "").strip())


def _empty_counters() -> CounterMapT:
    """Return initialized counters for a backfill run."""
    return {
        "considered": 0,
        "updated": 0,
        "would_update": 0,
        "skipped_existing": 0,
        "skipped_no_match": 0,
        "skipped_ambiguous": 0,
    }


def _counter_key(action: str) -> str:
    """Map report actions to summary counters."""
    if action in {"updated", "would_update", "skipped_no_match", "skipped_ambiguous"}:
        return action
    if action == "skipped_existing_description":
        return "skipped_existing"
    return "skipped_no_match"


__all__ = [
    "BackfillSummaryT",
    "REPORT_HEADERS",
    "backfill_course_descriptions",
]
