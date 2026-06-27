"""Reusable metrics for academic leader dashboards."""

from __future__ import annotations

from typing import TypeAlias, TypedDict

from django.db.models import QuerySet

from app.academics.models.curriculum import Curriculum
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.website.services.academic_dashboard_programs import program_stack_chart
from app.website.services.academic_dashboard_schedule import schedule_rows

DashboardContextT: TypeAlias = dict[str, object]


class WorkloadCountT(TypedDict):
    """Mutable workload counts for one program."""

    program: str
    sections: int
    faculty_ids: set[int]
    credits: int


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

    return [
        {
            "program": row["program"],
            "sections": row["sections"],
            "faculty": len(row["faculty_ids"]),
            "credits": row["credits"],
        }
        for row in sorted(counts.values(), key=lambda item: item["program"])
    ]


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
        "schedule_rows": schedule_rows(curricula, semester),
    }


__all__ = ["DashboardContextT", "academic_chart_context"]
