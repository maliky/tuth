"""Schedule row helpers for academic leader dashboards."""

from __future__ import annotations

from collections import defaultdict
from typing import TypedDict

from django.db.models import QuerySet

from app.academics.models.curriculum import Curriculum
from app.timetable.choices import WEEKDAYS_NUMBER
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester


class ScheduleMetricT(TypedDict):
    """One schedule coverage metric."""

    label: str
    value: str


class ScheduleSlotT(TypedDict):
    """One timetable slot grouping scoped section sessions."""

    weekday: str
    time: str
    room: str
    sections: str
    faculty: str
    sort_key: tuple[int, str, str]


class ScheduleSectionT(TypedDict):
    """One full section coverage row."""

    program: str
    course: str
    title: str
    section: str
    faculty: str
    seats: str
    utilization: str
    placement: str
    status: str
    status_class: str


class ScheduleCoverageT(TypedDict):
    """Full schedule coverage payload for academic dashboards."""

    metrics: list[ScheduleMetricT]
    slots: list[ScheduleSlotT]
    sections: list[ScheduleSectionT]
    has_sections: bool
    has_slots: bool


def _weekday_label(weekday: int) -> str:
    """Return a safe weekday label."""
    try:
        return WEEKDAYS_NUMBER(weekday).label
    except ValueError:
        return "TBA"


def _pct(value: int, total: int) -> str:
    """Return one-decimal utilization text."""
    return f"{(100 * value / total):.1f}%" if total else "0.0%"


def _faculty_name(section: Section) -> str:
    """Return the section faculty display name."""
    if section.faculty_id and section.faculty is not None:
        return section.faculty.staff_profile.long_name or "TBA"
    return "TBA"


def _session_label(session) -> tuple[str, bool, ScheduleSlotT | None]:
    """Return display text, placement state, and optional slot row for one session."""
    schedule = session.schedule
    room = str(session.room) if session.room_id else "TBA"
    weekday = int(schedule.weekday) if schedule and schedule.weekday is not None else 0
    weekday_label = _weekday_label(weekday)
    start = (
        schedule.start_time.strftime("%H:%M") if schedule and schedule.start_time else ""
    )
    end = schedule.end_time.strftime("%H:%M") if schedule and schedule.end_time else ""
    time_label = f"{start}-{end}" if start and end else "TBA"
    placed = bool(weekday and start and end and session.room_id)
    label = f"{weekday_label} {time_label} · {room}" if placed else "TBA"
    if not placed:
        return label, False, None
    slot: ScheduleSlotT = {
        "weekday": weekday_label,
        "time": time_label,
        "room": room,
        "sections": "",
        "faculty": "",
        "sort_key": (weekday, time_label, room),
    }
    return label, True, slot


def _section_label(section: Section) -> str:
    """Return the compact section label used in slot summaries."""
    course = section.curriculum_course.course
    return f"{course.short_code or course.code}:s{section.number:02d}"


def _section_placement(section: Section) -> tuple[str, bool, list[ScheduleSlotT]]:
    """Return placement text, section placement state, and slot rows."""
    labels: list[str] = []
    slots: list[ScheduleSlotT] = []
    section_placed = False
    for session in section.sessions.all():
        label, placed, slot = _session_label(session)
        labels.append(label)
        section_placed = section_placed or placed
        if slot is not None:
            slots.append(slot)
    return "; ".join(labels) or "TBA", section_placed, slots


def _dashboard_sections(
    curricula: QuerySet[Curriculum],
    semester: Semester,
) -> QuerySet[Section]:
    """Return scoped sections with relations required for dashboard rendering."""
    return (
        Section.objects.filter(
            semester=semester,
            curriculum_course__curriculum__in=curricula,
        )
        .select_related(
            "curriculum_course__curriculum",
            "curriculum_course__course",
            "curriculum_course__credit_hours",
            "faculty__staff_profile",
        )
        .prefetch_related("sessions__schedule", "sessions__room__space")
        .order_by(
            "curriculum_course__curriculum__short_name",
            "curriculum_course__course__short_code",
            "number",
            "id",
        )
    )


def _metric(label: str, value: object) -> ScheduleMetricT:
    """Return a normalized metric row."""
    return {"label": label, "value": str(value)}


def schedule_coverage(
    curricula: QuerySet[Curriculum],
    semester: Semester,
) -> ScheduleCoverageT:
    """Return full section coverage and timetable slot data."""
    sections = list(_dashboard_sections(curricula, semester))
    placed_section_ids: set[int] = set()
    slot_groups: dict[tuple[int, str, str], dict[str, set[str] | ScheduleSlotT]] = {}
    section_rows: list[ScheduleSectionT] = []
    total_registered = 0
    total_capacity = 0

    for section in sections:
        course = section.curriculum_course.course
        faculty = _faculty_name(section)
        placement, placed, slots = _section_placement(section)
        if placed and section.id:
            placed_section_ids.add(section.id)
        total_registered += int(section.current_registrations or 0)
        total_capacity += int(section.max_seats or 0)
        for slot in slots:
            key = slot["sort_key"]
            group = slot_groups.setdefault(
                key,
                {"slot": slot, "sections": set(), "faculty": set()},
            )
            sections_set = group["sections"]
            faculty_set = group["faculty"]
            if isinstance(sections_set, set):
                sections_set.add(_section_label(section))
            if isinstance(faculty_set, set):
                faculty_set.add(faculty)
        section_rows.append(
            {
                "program": section.curriculum_course.curriculum.short_name,
                "course": str(course.short_code or course.code),
                "title": course.title or "",
                "section": f"{section.number:02d}",
                "faculty": faculty,
                "seats": f"{section.current_registrations}/{section.max_seats}",
                "utilization": _pct(
                    int(section.current_registrations or 0),
                    int(section.max_seats or 0),
                ),
                "placement": placement,
                "status": "Placed" if placed else "TBA",
                "status_class": "success" if placed else "warning",
            }
        )

    slots = [_finalize_slot(group) for group in slot_groups.values()]
    slots.sort(key=lambda row: row["sort_key"])
    placed_total = len(placed_section_ids)
    return {
        "metrics": [
            _metric("Sections", len(sections)),
            _metric("Placed", placed_total),
            _metric("TBA", len(sections) - placed_total),
            _metric("Seats", f"{total_registered}/{total_capacity}"),
            _metric("Utilization", _pct(total_registered, total_capacity)),
        ],
        "slots": slots,
        "sections": section_rows,
        "has_sections": bool(section_rows),
        "has_slots": bool(slots),
    }


def _finalize_slot(group: dict[str, set[str] | ScheduleSlotT]) -> ScheduleSlotT:
    """Return one display-ready timetable slot row."""
    slot = group["slot"]
    if not isinstance(slot, dict):
        raise TypeError("Slot group is missing schedule data.")
    sections = group["sections"]
    faculty = group["faculty"]
    section_labels = sorted(sections) if isinstance(sections, set) else []
    faculty_labels = sorted(faculty) if isinstance(faculty, set) else []
    return {
        **slot,
        "sections": ", ".join(section_labels),
        "faculty": ", ".join(faculty_labels),
    }


def schedule_rows(
    curricula: QuerySet[Curriculum],
    semester: Semester,
    *,
    limit: int = 10,
) -> list[dict[str, str]]:
    """Return current teaching schedule rows for backward-compatible callers."""
    return [
        {
            "program": row["program"],
            "course": row["course"],
            "section": row["section"],
            "faculty": row["faculty"],
            "placement": row["placement"],
        }
        for row in schedule_coverage(curricula, semester)["sections"][:limit]
    ]


__all__ = ["ScheduleCoverageT", "schedule_coverage", "schedule_rows"]
