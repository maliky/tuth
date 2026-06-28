"""Reusable metrics for academic leader dashboards."""

from __future__ import annotations

from typing import TypeAlias, TypedDict

from django.db.models import QuerySet

from app.academics.models.curriculum import Curriculum
from app.people.models.faculty import FacultyWorkloadSnapshot
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.website.services.academic_dashboard_programs import program_stack_chart
from app.website.services.academic_dashboard_schedule import (
    schedule_coverage,
    schedule_rows,
)

DashboardContextT: TypeAlias = dict[str, object]


class WorkloadCountT(TypedDict):
    """Mutable workload counts for one program."""

    program: str
    sections: int
    faculty_ids: set[int]
    credits: int


class WorkloadSnapshotT(TypedDict):
    """Faculty workload snapshot data used for overload display."""

    faculty_name: str
    overload: bool


def _program_workloads(
    curricula: QuerySet[Curriculum],
    semester: Semester,
) -> list[dict[str, object]]:
    """Return program-level faculty workload summaries for one semester."""
    sections = (
        Section.objects.filter(
            semester=semester,
            curriculum_course__curriculum__in=curricula,
        )
        .select_related(
            "curriculum_course__curriculum",
            "curriculum_course__credit_hours",
            "faculty__staff_profile",
        )
        .order_by("curriculum_course__curriculum__short_name")
    )
    counts: dict[int, WorkloadCountT] = {}
    for section in sections:
        curriculum = section.curriculum_course.curriculum
        data = counts.setdefault(
            curriculum.id,
            {
                "program": curriculum.short_name,
                "sections": 0,
                "faculty_ids": set(),
                "credits": 0,
            },
        )
        data["sections"] += 1
        if section.faculty_id:
            data["faculty_ids"].add(section.faculty_id)
        data["credits"] += int(section.curriculum_course.credit_hours.code)

    snapshots = _snapshot_map(
        semester,
        {faculty_id for row in counts.values() for faculty_id in row["faculty_ids"]},
    )
    return [
        {
            "program": row["program"],
            "sections": row["sections"],
            "faculty": len(row["faculty_ids"]),
            "credits": row["credits"],
            **_overload_summary(row, snapshots),
        }
        for row in sorted(counts.values(), key=lambda item: item["program"])
    ]


def _snapshot_map(
    semester: Semester,
    faculty_ids: set[int],
) -> dict[int, WorkloadSnapshotT]:
    """Return workload snapshots keyed by faculty id."""
    if not faculty_ids:
        return {}
    snapshots = (
        FacultyWorkloadSnapshot.objects.filter(
            semester=semester,
            faculty_id__in=faculty_ids,
        )
        .select_related("faculty__staff_profile")
        .order_by("faculty_id")
    )
    return {
        snapshot.faculty_id: {
            "faculty_name": snapshot.faculty.staff_profile.long_name or "TBA",
            "overload": snapshot.overload_flag,
        }
        for snapshot in snapshots
    }


def _overload_summary(
    row: WorkloadCountT,
    snapshots: dict[int, WorkloadSnapshotT],
) -> dict[str, object]:
    """Return display fields for workload overload status."""
    faculty_ids = row["faculty_ids"]
    if not faculty_ids:
        return {
            "overload_label": "No faculty",
            "overload_detail": "No assigned faculty for this program.",
            "overload_state": "muted",
        }
    overload_names = sorted(
        snapshots[faculty_id]["faculty_name"]
        for faculty_id in faculty_ids
        if faculty_id in snapshots and snapshots[faculty_id]["overload"]
    )
    snapshot_count = sum(1 for faculty_id in faculty_ids if faculty_id in snapshots)
    if overload_names:
        return {
            "overload_label": f"{len(overload_names)} overload",
            "overload_detail": ", ".join(overload_names),
            "overload_state": "danger",
        }
    if snapshot_count:
        return {
            "overload_label": "No overload",
            "overload_detail": f"{snapshot_count} workload snapshot(s) reviewed.",
            "overload_state": "success",
        }
    return {
        "overload_label": "No snapshot",
        "overload_detail": "Workload snapshot is not available for this semester.",
        "overload_state": "muted",
    }


def academic_chart_context(
    *,
    title: str,
    scope_label: str,
    curricula: QuerySet[Curriculum],
    semester: Semester,
) -> DashboardContextT:
    """Build common chart, workload, and schedule context."""
    return {
        "title": title,
        "scope_label": scope_label,
        "program_stack_chart": program_stack_chart(curricula, semester),
        "program_workloads": _program_workloads(curricula, semester),
        "schedule_coverage": schedule_coverage(curricula, semester),
        "schedule_rows": schedule_rows(curricula, semester),
    }


__all__ = ["DashboardContextT", "academic_chart_context"]
