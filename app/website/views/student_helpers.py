"""Shared helpers for student-facing views."""

from __future__ import annotations

from typing import cast

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied

from app.people.models.student import Student
from app.shared.admin.core import get_current_semester
from app.timetable.models.semester import Semester


def _require_student(user: User | AnonymousUser) -> Student:
    """Return the related Student or abort early."""
    student = getattr(user, "student", None)
    if student is None:
        raise PermissionDenied("User has no Student profile.")
    return cast(Student, student)  # <— only cast once, in one place


def _resolve_semester(
    student: Student, requested_semester_id: str | None
) -> tuple[Semester | None, list[Semester]]:
    """Return the semester that should drive course availability."""
    open_semesters = (
        Semester.objects.filter(status_id=Semester.REGISTRATION_OPEN_CODES)
        .select_related("academic_year", "status")
        .order_by("academic_year__start_date", "number")
    )
    semester: Semester | None = None

    # we look if requested_semester_id is part of the open_semester
    if requested_semester_id:
        semester = next(
            (sem for sem in open_semesters if str(sem.id) == str(requested_semester_id)),
            None,
        )

    # if not we return the first open semester
    if semester is None and open_semesters:
        semester = open_semesters.first()

    # or the student last enrolled semester or the current one
    if semester is None:
        semester = student.last_enrolled_semester or get_current_semester()
    return semester, list(open_semesters)
