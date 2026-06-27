"""Schedule row helpers for academic leader dashboards."""

from __future__ import annotations

from django.db.models import QuerySet

from app.academics.models.curriculum import Curriculum
from app.timetable.choices import WEEKDAYS_NUMBER
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester


def _format_schedule(section: Section) -> str:
    """Return compact room and time placement for a section."""
    parts: list[str] = []
    for session in section.sessions.all():
        schedule = session.schedule
        room = str(session.room) if session.room else "TBA"
        if schedule and schedule.weekday is not None:
            try:
                weekday = WEEKDAYS_NUMBER(schedule.weekday).label
            except ValueError:
                weekday = "TBA"
            start = schedule.start_time.strftime("%H:%M") if schedule.start_time else ""
            end = schedule.end_time.strftime("%H:%M") if schedule.end_time else ""
            time_label = f"{weekday} {start}-{end}".strip()
        else:
            time_label = "TBA"
        parts.append(f"{room} · {time_label}")
    return "; ".join(parts) or "TBA"


def schedule_rows(
    curricula: QuerySet[Curriculum],
    semester: Semester,
    *,
    limit: int = 10,
) -> list[dict[str, str]]:
    """Return current teaching schedule rows for dashboard display."""
    sections = (
        Section.objects.filter(
            semester=semester,
            curriculum_course__curriculum__in=curricula,
        )
        .select_related(
            "curriculum_course__curriculum",
            "curriculum_course__course",
            "faculty__staff_profile",
        )
        .prefetch_related("sessions__schedule", "sessions__room__space")
        .order_by("curriculum_course__curriculum__short_name", "number", "id")[:limit]
    )
    rows: list[dict[str, str]] = []
    for section in sections:
        course = section.curriculum_course.course
        faculty_name = "TBA"
        if section.faculty_id and section.faculty is not None:
            faculty_name = section.faculty.staff_profile.long_name or "TBA"
        rows.append(
            {
                "program": section.curriculum_course.curriculum.short_name,
                "course": str(course.short_code or course.code),
                "section": f"{section.number:02d}",
                "faculty": faculty_name,
                "placement": _format_schedule(section),
            }
        )
    return rows


__all__ = ["schedule_rows"]
