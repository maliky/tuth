"""Website views for the student dashboard."""

from __future__ import annotations

from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from app.people.models.student import Student
from app.registry.choices import StatusRegistration
from app.registry.models.registration import Registration
from app.shared.status import StatusHistory
from app.timetable.models.section import Section
from app.people.forms.person import StudentForm


def landing_page(request: HttpRequest) -> HttpResponse:
    """Render the website landing page."""
    return render(request, "website/landing.html")


def _require_student(user: User | AnonymousUser) -> Student:
    """Return the related Student or abort early."""
    student = getattr(user, "student", None)
    if student is None:
        raise PermissionDenied("User has no Student profile.")
    return cast(Student, student)  # <— only cast once, in one place


def course_dashboard(request: HttpRequest) -> HttpResponse:
    """Allow a student to manage their course registrations."""
    # rely on the authenticated user's Student profile
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
            # record the change before deleting the registration
            tables = connection.introspection.table_names()
            if StatusHistory._meta.db_table in tables:
                reg.status_history.create(
                    status=StatusRegistration.REMOVE,
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
        "statuses": StatusRegistration.choices,
    }

    return render(request, "website/course_dashboard.html", context)


@permission_required("people.add_student", raise_exception=True)
def create_student(request: HttpRequest) -> HttpResponse:
    """Allow enrollment officers to create a new student profile."""

    if request.method == "POST":
        form = StudentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Student created successfully.")
            return redirect("create_student")
    else:
        form = StudentForm()

    return render(request, "website/create_student.html", {"form": form})
