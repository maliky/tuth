"""Student-facing landing views and shared helpers."""

from __future__ import annotations

from typing import cast

from django.contrib import messages
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from app.people.models.student import Student
from app.registry.models.registration import Registration, RegistrationStatus
from app.shared.status import StatusHistory
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.timetable.utils import get_current_semester


def landing_page(request: HttpRequest) -> HttpResponse:
    """Render the website landing page."""
    return render(request, "website/landing.html")


def _require_student(user: User | AnonymousUser) -> Student:
    """Return the related Student or abort early."""
    student = getattr(user, "student", None)
    if student is None and not user.is_superuser:
        raise PermissionDenied("User has no Student profile.")
    return cast(Student, student)  # <— only cast once, in one place


def _resolve_semester(student: Student, requested_semester_id: str | None):
    """Return the semester that should drive course availability."""
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
        semester = student.current_enrolled_semester or get_current_semester()
    return semester, list(open_semesters)


def course_dashboard(request: HttpRequest) -> HttpResponse:
    """Allow a student to manage their course registrations."""
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
            tables = connection.introspection.table_names()
            if StatusHistory._meta.db_table in tables:
                reg.status_history.create(
                    status="remove",
                    author=request.user,
                )
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM registry_registration WHERE id = %s",
                    [reg_id],
                )
            messages.success(request, "Registration removed.")
            return redirect("course_dashboard")

        if action == "update":
            reg_id = request.POST.get("registration_id")
            reg = get_object_or_404(Registration, pk=reg_id, student=student)
            reg.status = request.POST.get("status")  # type: ignore[assignment]
            reg.save()
            messages.success(request, "Registration updated.")
            return redirect("course_dashboard")

    registrations = Registration.objects.filter(student=student)
    available_sections = Section.objects.exclude(
        id__in=registrations.values_list("section_id", flat=True)
    )

    context = {
        "registrations": registrations,
        "available_sections": available_sections,
        "statuses": RegistrationStatus.objects.all(),
    }

    return render(request, "website/course_dashboard.html", context)
