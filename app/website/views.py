"""Website views for the student dashboard."""

from __future__ import annotations

from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from app.people.models.student import Student
from app.registry.choices import StatusRegistration
from app.registry.models.registration import Registration
from app.timetable.models.section import Section
from app.finance.models.financial_record import SectionFee
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


def registration_dashboard(request: HttpRequest) -> HttpResponse:
    """Display and manage course section reservations for the student."""

    # rely on the authenticated user's Student profile
    student = _require_student(request.user)

    if request.method == "POST":
        action = request.POST.get("action")
        selected = request.POST.getlist("sections")

        if action == "reserve":
            for sec_id in selected:
                section = get_object_or_404(Section, pk=sec_id)
                # create or update registration with pending status
                Registration.objects.update_or_create(
                    student=student,
                    section=section,
                    defaults={"status": StatusRegistration.PENDING},
                )
            messages.success(request, "Reservation saved.")
            return redirect("registration_dashboard")

        if action == "cancel":
            regs = Registration.objects.filter(
                student=student, section_id__in=selected
            )
            regs.delete()
            messages.success(request, "Reservation cancelled.")
            return redirect("registration_dashboard")

    courses = student.allowed_courses()
    sections = (
        Section.objects.filter(program__course__in=courses)
        .select_related("program__course")
        .prefetch_related("sessions__schedule")
    )

    # gather any additional fees per section for quick lookup
    fees = {
        fee.section_id: fee.amount
        for fee in SectionFee.objects.filter(section__in=sections)
    }

    sections_by_course: dict = {}
    for sec in sections:
        course = sec.program.course
        # attach fee amount so templates can calculate totals
        sec.fee_amount = fees.get(sec.id, 0)
        sections_by_course.setdefault(course, []).append(sec)

    existing = set(
        Registration.objects.filter(student=student).values_list(
            "section_id", flat=True
        )
    )

    context = {
        "sections_by_course": sections_by_course,
        "existing": existing,
        "fees": fees,
    }

    return render(request, "website/registration_dashboard.html", context)


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
