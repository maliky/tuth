"""Backfill global prerequisite edges from TUCurricula requirement rows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from django.db import transaction

from app.academics.course_prerequisite_sources import (
    CourseMapT,
    SourceCourseMapT,
    SourcePrerequisiteT,
    current_course_maps,
    load_source_courses,
    load_source_prerequisites,
    matching_courses,
    representative_course,
    source_course,
)
from app.academics.models.course import Course
from app.academics.models.prerequisite import Prerequisite
from app.shared.source_truth.io import RowT, write_tsv

CounterMapT: TypeAlias = dict[str, int]

REPORT_HEADERS = (
    "target_source_key",
    "required_source_key",
    "target_course_id",
    "target_course_code",
    "required_course_id",
    "required_course_code",
    "action",
    "reason",
    "target_match_count",
    "required_match_count",
    "source_files",
)


@dataclass(frozen=True)
class PrerequisiteBackfillSummaryT:
    """Summary of one global prerequisite backfill pass."""

    source_pairs: int
    created: int
    would_create: int
    skipped_existing: int
    skipped_unresolved_target: int
    skipped_unresolved_required: int
    skipped_self: int
    report_path: Path | None


def backfill_global_prerequisites(
    *,
    import_dir: Path,
    report_path: Path | None = None,
    apply: bool = False,
) -> PrerequisiteBackfillSummaryT:
    """Create global prereq_all edges from TUCurricula source rows."""
    source_courses = load_source_courses(import_dir)
    source_prereqs = load_source_prerequisites(import_dir)
    current_by_key, current_by_number = current_course_maps()
    counters = _empty_counters(source_pairs=len(source_prereqs))
    report_rows: list[RowT] = []

    if apply:
        with transaction.atomic():
            _run_backfill(
                source_courses=source_courses,
                source_prereqs=source_prereqs,
                current_by_key=current_by_key,
                current_by_number=current_by_number,
                counters=counters,
                report_rows=report_rows,
                apply=True,
            )
    else:
        _run_backfill(
            source_courses=source_courses,
            source_prereqs=source_prereqs,
            current_by_key=current_by_key,
            current_by_number=current_by_number,
            counters=counters,
            report_rows=report_rows,
            apply=False,
        )

    if report_path is not None:
        write_tsv(report_path, REPORT_HEADERS, report_rows)
    return _summary(counters, report_path)


def _run_backfill(
    *,
    source_courses: SourceCourseMapT,
    source_prereqs: list[SourcePrerequisiteT],
    current_by_key: CourseMapT,
    current_by_number: CourseMapT,
    counters: CounterMapT,
    report_rows: list[RowT],
    apply: bool,
) -> None:
    """Resolve source edges into current Course rows and optionally persist them."""
    for source_prereq in source_prereqs:
        target_source = source_course(source_prereq.target_key, source_courses)
        required_source = source_course(source_prereq.required_key, source_courses)
        target_courses = matching_courses(
            target_source, current_by_key, current_by_number
        )
        required_courses = matching_courses(
            required_source, current_by_key, current_by_number
        )
        if not target_courses:
            _skip_unresolved(source_prereq, counters, report_rows, "target")
            continue
        if not required_courses:
            _skip_unresolved(source_prereq, counters, report_rows, "required")
            continue
        required_course = representative_course(required_courses, required_source.key)
        for target_course in target_courses:
            _persist_edge(
                source_prereq=source_prereq,
                target_course=target_course,
                required_course=required_course,
                target_count=len(target_courses),
                required_count=len(required_courses),
                counters=counters,
                report_rows=report_rows,
                apply=apply,
            )


def _persist_edge(
    *,
    source_prereq: SourcePrerequisiteT,
    target_course: Course,
    required_course: Course,
    target_count: int,
    required_count: int,
    counters: CounterMapT,
    report_rows: list[RowT],
    apply: bool,
) -> None:
    """Create or report one global prerequisite edge."""
    if target_course.id == required_course.id:
        action = "skipped_self"
        reason = "target course equals required course"
    elif Prerequisite.objects.filter(
        curriculum__isnull=True,
        course=target_course,
        prerequisite_course=required_course,
    ).exists():
        action = "skipped_existing"
        reason = "global prerequisite already exists"
    elif apply:
        Prerequisite.objects.create(
            curriculum=None,
            course=target_course,
            prerequisite_course=required_course,
        )
        action = "created"
        reason = "global prereq_all edge created"
    else:
        action = "would_create"
        reason = "dry-run global prereq_all edge"
    counters[action] += 1
    report_rows.append(
        _report_row(
            source_prereq=source_prereq,
            target_course=target_course,
            required_course=required_course,
            action=action,
            reason=reason,
            target_count=target_count,
            required_count=required_count,
        )
    )


def _skip_unresolved(
    source_prereq: SourcePrerequisiteT,
    counters: CounterMapT,
    report_rows: list[RowT],
    side: str,
) -> None:
    """Record an unresolved source-course side."""
    action = f"skipped_unresolved_{side}"
    counters[action] += 1
    report_rows.append(
        _report_row(
            source_prereq=source_prereq,
            target_course=None,
            required_course=None,
            action=action,
            reason=f"unresolved {side} course",
            target_count=0,
            required_count=0,
        )
    )


def _report_row(
    *,
    source_prereq: SourcePrerequisiteT,
    target_course: Course | None,
    required_course: Course | None,
    action: str,
    reason: str,
    target_count: int,
    required_count: int,
) -> RowT:
    """Build one audit report row."""
    return {
        "target_source_key": source_prereq.target_key,
        "required_source_key": source_prereq.required_key,
        "target_course_id": str(target_course.id) if target_course else "",
        "target_course_code": _course_code(target_course),
        "required_course_id": str(required_course.id) if required_course else "",
        "required_course_code": _course_code(required_course),
        "action": action,
        "reason": reason,
        "target_match_count": str(target_count),
        "required_match_count": str(required_count),
        "source_files": source_prereq.source_files,
    }


def _course_code(course: Course | None) -> str:
    """Return a report-friendly course code."""
    if course is None:
        return ""
    return course.short_code or course.code or ""


def _empty_counters(*, source_pairs: int) -> CounterMapT:
    """Return initialized counters for one run."""
    return {
        "source_pairs": source_pairs,
        "created": 0,
        "would_create": 0,
        "skipped_existing": 0,
        "skipped_unresolved_target": 0,
        "skipped_unresolved_required": 0,
        "skipped_self": 0,
    }


def _summary(
    counters: CounterMapT, report_path: Path | None
) -> PrerequisiteBackfillSummaryT:
    """Build a typed summary from mutable counters."""
    return PrerequisiteBackfillSummaryT(
        source_pairs=counters["source_pairs"],
        created=counters["created"],
        would_create=counters["would_create"],
        skipped_existing=counters["skipped_existing"],
        skipped_unresolved_target=counters["skipped_unresolved_target"],
        skipped_unresolved_required=counters["skipped_unresolved_required"],
        skipped_self=counters["skipped_self"],
        report_path=report_path,
    )


__all__ = [
    "PrerequisiteBackfillSummaryT",
    "REPORT_HEADERS",
    "backfill_global_prerequisites",
]
