"""Shared helpers for student-facing views."""

from __future__ import annotations

from typing import Optional, cast

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from app.finance.models.payment import Payment
from app.people.models.student import Student
from app.timetable.models.semester import Semester


def _require_std(user: User | AnonymousUser) -> Student:
    """Return the related Student or abort early."""
    student = getattr(user, "student", None)
    if student is None:
        raise PermissionDenied("User has no Student profile.")
    return cast(Student, student)  # <— only cast once, in one place


def _resolve_sem(
    student: Student, requested_semester_id: Optional[str]
) -> tuple[Optional[Semester], list[Semester]]:
    """Return the semester that should drive course availability."""
    open_semesters = (
        Semester.objects.filter(status_id=Semester.REGISTRATION_OPEN_CODES)
        .select_related("academic_year", "status")
        .order_by("academic_year__start_date", "number")
    )
    semester: Optional[Semester] = None

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
        semester = student.last_enrolled_semester or Semester.get_current_sem()
    return semester, list(open_semesters)


def _build_std_profile(student: Student) -> dict[str, str]:
    """Return the student profile block for portal templates."""
    academic_year = "Not assigned"
    if student.entry_semester:
        academic_year = (
            f"{student.entry_semester.academic_year.code} · "
            f"Semester {student.entry_semester.number}"
        )
    avatar_url = ""
    if getattr(student, "photo", None) and student.photo:
        avatar_url = student.photo.url
    return {
        "name": student.long_name or student.user.get_full_name() or student.username,
        "student_id": student.student_id or "Pending ID",
        "academic_year": academic_year,
        "curriculum": student.curriculum.long_name or student.curriculum.short_name,
        "avatar": avatar_url,
    }


def _build_sidebar_links(
    active_label: str,
    *,
    student: Student | None = None,
) -> list[dict[str, str | bool]]:
    """Return sidebar links with the requested active label."""
    dashboard_url = reverse("student_dashboard")
    # Use the current semester for the payment statement shortcut when possible.
    payment_statement_url = ""
    payment_semester_id = None
    if student is not None:
        payment_semester_id = (
            Payment.objects.filter(
                student_semester_invoice__student=student, amount_paid__gt=0
            )
            .order_by("-id")
            .values_list("student_semester_invoice__semester_id", flat=True)
            .first()
        )
    if payment_semester_id:
        payment_statement_url = reverse(
            "std_payment_receipt",
            args=[payment_semester_id],
        )
    else:
        current_semester = Semester.get_current_sem()
        if current_semester:
            payment_statement_url = reverse(
                "std_payment_receipt",
                args=[current_semester.id],
            )
    links: list[dict[str, str | bool]] = [
        {"label": "Dashboard", "href": dashboard_url, "active": False},
        {
            "label": "Course Registration",
            "href": f"{dashboard_url}#courses",
            "active": False,
        },
        {
            "label": "Old Course and grades",
            "href": f"{dashboard_url}#records",
            "active": False,
        },
        {
            "label": "Payment statement",
            "href": payment_statement_url or "#",
            "active": False,
        },
        {
            "label": "Invoice statement",
            "href": reverse("std_invoice_statement"),
            "active": False,
        },
        {"label": "Support", "href": f"{dashboard_url}#support", "active": False},
    ]
    for link in links:
        if link["label"] == active_label:
            link["active"] = True
    return links
