"""Student-facing landing views and shared helpers."""

from __future__ import annotations

from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from app.people.models.student import Student
from app.registry.models.registration import Registration, RegistrationStatus
from app.shared.admin.core import get_current_semester
from app.shared.types import LookUpType, RegistrationQuery, SectionQuery
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester


def landing_page(request: HttpRequest) -> HttpResponse:
    """Render the website landing page.

    Args:
        request: Incoming HTTP request.

    Returns:
        Rendered landing page response.
    """
    return render(request, "website/landing.html")


def _require_student(user: User | AnonymousUser) -> Student:
    """Return the related Student or abort early.

    Args:
        user: Authenticated Django user.

    Returns:
        Student profile tied to the user.

    Raises:
        PermissionDenied: If the user has no student profile.

    Example:
        >>> student = _require_student(request.user)
    """
    student = getattr(user, "student", None)
    if student is None:
        raise PermissionDenied("User has no Student profile.")
    return cast(Student, student)  # <— only cast once, in one place


def _resolve_semester(
    student: Student, requested_semester_id: str | None
) -> tuple[Semester | None, list[Semester]]:
    """Return the semester that should drive course availability.

    Args:
        student: Student record requesting the dashboard.
        requested_semester_id: Semester id from query parameters, if provided.

    Returns:
        A tuple of (active semester, available semesters).
    """
    open_semesters = (
        Semester.objects.filter(status_id__in=Semester.REGISTRATION_OPEN_CODES)
        .select_related("academic_year", "status")
        .order_by("academic_year__start_date", "number")
    )
    semester: Semester | None = None
    if requested_semester_id:
        semester = next(
            (sem for sem in open_semesters if str(sem.id) == str(requested_semester_id)),
            None,
        )
    if semester is None and open_semesters:
        semester = open_semesters.first()
    if semester is None:
        semester = student.last_enrolled_semester or get_current_semester()
    return semester, list(open_semesters)


def _get_registration_status_choices() -> LookUpType:
    """Build status choices for course registration.

    Returns:
        Sequence of (code, label) tuples.
    """
    return [
        (status.code, status.label)
        for status in RegistrationStatus.objects.all().order_by("code")
    ]


def _get_student_registrations(student: Student) -> RegistrationQuery:
    """Return registrations for the current student.

    Args:
        student: Student profile requesting the list.

    Returns:
        QuerySet of registrations tied to the student.

    Example:
        >>> regs = _get_student_registrations(student)
    """
    return Registration.objects.filter(student=student).select_related(
        "section", "status"
    )


def _get_available_sections(registrations: RegistrationQuery) -> SectionQuery:
    """Return sections the student can still add.

    Args:
        registrations: Current registrations to exclude.

    Returns:
        QuerySet of sections not yet registered by the student.
    """
    return Section.objects.exclude(
        id__in=registrations.values_list("section_id", flat=True)
    )


def _update_registration_status(
    registration: Registration, status_code: str | None
) -> bool:
    """Update the registration status if the code is valid.

    Args:
        registration: Registration to update.
        status_code: Status code from the form submission.

    Returns:
        True when the update succeeds, otherwise False.

    Example:
        >>> updated = _update_registration_status(reg, "approved")
    """
    if not status_code:
        return False
    status = RegistrationStatus.objects.filter(code=status_code).first()
    if not status:
        return False
    registration.status = status
    registration.save(update_fields=["status"])
    return True


@login_required
def course_dashboard(request: HttpRequest) -> HttpResponse:
    """Allow a student to manage their course registrations.

    Args:
        request: Incoming HTTP request.

    Returns:
        Rendered course dashboard response.
    """
    student = _require_student(request.user)
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add":
            section_id = request.POST.get("section_id")
            section = get_object_or_404(Section, pk=section_id)
            Registration.objects.create(student=student, section=section)
            messages.success(request, "Course added successfully.")
            return redirect("course_dashboard")

        if action == "remove":
            reg_id = request.POST.get("registration_id")
            reg = get_object_or_404(Registration, pk=reg_id, student=student)
            reg.status_history.create(
                status="remove",
                author=request.user,
            )
            # Keep ORM delete so audit trails/signals are preserved.
            reg.delete()
            messages.success(request, "Registration removed.")
            return redirect("course_dashboard")

        if action == "update":
            reg_id = request.POST.get("registration_id")
            reg = get_object_or_404(Registration, pk=reg_id, student=student)
            status_code = request.POST.get("status")
            if _update_registration_status(reg, status_code):
                messages.success(request, "Registration updated.")
            else:
                messages.error(request, "Unknown registration status.")
            return redirect("course_dashboard")

    registrations = _get_student_registrations(student)
    available_sections = _get_available_sections(registrations)

    context = {
        "registrations": registrations,
        "available_sections": available_sections,
        "statuses": _get_registration_status_choices(),
    }

    return render(request, "website/course_dashboard.html", context)
