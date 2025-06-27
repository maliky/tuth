"""Website views for the student dashboard."""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.db import connection

from app.shared.status import StatusHistory

from app.registry.choices import StatusRegistration
from app.registry.models.registration import Registration
from app.timetable.models.section import Section


def landing_page(request: HttpRequest) -> HttpResponse:
    """Render the website landing page."""
    return render(request, "website/landing.html")


def course_dashboard(request: HttpRequest) -> HttpResponse:
    """Allow a student to manage their course registrations."""
    # rely on the authenticated user's Student profile
    student = request.user.student

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
            reg.status = request.POST.get("status")
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
