"""Student section detail views."""

from __future__ import annotations

from datetime import time
from typing import Optional

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from app.registry.models.registration import Registration
from app.timetable.choices import WEEKDAYS_NUMBER

from .student_helpers import (
    _build_sidebar_links,
    _build_student_profile,
    _require_student,
)


# > move this to an utils file probably in app/shared
def _format_time(value: Optional[time]) -> str:
    """Return a time string for schedule displays."""
    if value is None:
        return "—"
    return value.strftime("%H:%M")


@login_required
def student_section_detail(
    request: HttpRequest,
    section_id: int,
) -> HttpResponse:
    """Render a cleared section detail view for the current student."""
    student = _require_student(request.user)
    registration = (
        Registration.objects.filter(
            student=student,
            section_id=section_id,
            status_id__in={"cleared", "approved"},
        )
        .select_related(
            "section__semester__academic_year",
            "section__curriculum_course__course",
            "section__curriculum_course__credit_hours",
            "section__faculty__staff_profile__user",
        )
        .prefetch_related("section__sessions__schedule", "section__sessions__room")
        .first()
    )
    if registration is None:
        raise Http404("Section not found.")

    section = registration.section
    schedule_rows: list[dict[str, str]] = []
    for session in section.sessions.all():
        schedule = session.schedule
        weekday_label = "TBA"
        if schedule and schedule.weekday is not None:
            try:
                weekday_label = WEEKDAYS_NUMBER(schedule.weekday).label
            except ValueError:
                weekday_label = "TBA"
        start_label = _format_time(schedule.start_time if schedule else None)
        end_label = _format_time(schedule.end_time if schedule else None)
        room_label = session.room.code if session.room else "TBA"
        schedule_rows.append(
            {
                "weekday": weekday_label,
                "time": f"{start_label}–{end_label}",
                "room": room_label,
            }
        )

    faculty_label = "TBA"
    if section.faculty and section.faculty.staff_profile:
        faculty_label = section.faculty.staff_profile.user.get_full_name() or str(
            section.faculty.staff_profile
        )

    context = {
        "student_profile": _build_student_profile(student),
        "sidebar_links": _build_sidebar_links("Course Registration", student=student),
        "section": {
            "code": section.course.short_code or section.course.code,
            "title": section.course.title or "",
            "semester": str(section.semester),
            "number": section.number,
            "credits": section.curriculum_course.credit_hours.code,
            "faculty": faculty_label,
            "status": registration.status.label if registration.status else "Cleared",
            "registered_on": registration.date_registered,
            "seats_total": section.max_seats,
            "seats_available": section.available_seats,
            "info": section.info,
            "schedule_rows": schedule_rows,
        },
    }
    return render(request, "website/student_section_detail.html", context)
