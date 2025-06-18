"""Website views for the student dashboard and reservation creation."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import ExpressionWrapper, F, IntegerField, QuerySet, Sum
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render

from app.finance.models.financial_record import FinancialRecord
from app.people.models.others import Student
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.shared.constants import StatusReservation
from app.timetable.models import Reservation, Section


def landing_page(request: HttpRequest) -> HttpResponse:
    """Render the website landing page."""
    return render(request, "website/landing.html")


@login_required
def create_reservation(request: HttpRequest, section_id: int) -> HttpResponseRedirect:
    """Reserve a section for the current student if possible."""
    user = cast(User, request.user)
    student = user.student
    section = get_object_or_404(Section, id=section_id)

    if Reservation.objects.filter(student=student, section=section).exists():
        messages.info(request, "You have already reserved this section.")
        return redirect("student_dashboard")

    if not section.has_available_seats():
        messages.error(request, "Section is full.")
        return redirect("student_dashboard")

    if not validate_credit_limit(student, section):
        messages.error(request, "Exceeded credit-hour limit.")
        return redirect("student_dashboard")

    reservation = Reservation(
        student=student, section=section, status=StatusReservation.REQUESTED
    )
    try:
        reservation.full_clean()
    except ValidationError as err:
        messages.error(request, str(err))
        return redirect("student_dashboard")

    reservation.save()
    messages.success(request, "Reservation successful.")
    return redirect("student_dashboard")


@login_required
def student_dashboard(request):
    """Display the student's reservations, registrations and fees."""
    user = cast(User, request.user)
    student = user.student

    if request.method == "POST":
        section_id = request.POST.get("section_id")
        if section_id:
            return create_reservation(request, section_id)

    available_sections: QuerySet[Section] = (
        Section.objects.annotate(
            seats_left=ExpressionWrapper(
                F("max_seats") - F("current_registrations"),  # type: ignore
                output_field=IntegerField(),
            )
        )
        .filter(seats_left__gt=0)
        .select_related("course")
    )

    reservations = (
        Reservation.objects.filter(student=student)
        .select_related("section__course")
        .order_by("-date_requested")
    )

    registrations = (
        Registration.objects.filter(student=student)
        .select_related("section__course")
        .order_by("-date_registered")
    )

    financial_record = FinancialRecord.objects.filter(student=student).first()
    outstanding_fees = (
        financial_record.total_due - financial_record.total_paid
        if financial_record
        else Decimal("0.00")
    )

    past_grades = (
        Grade.objects.filter(student=student)
        .select_related("section__course")
        .order_by("-graded_on")
    )

    context = {
        "available_sections": available_sections,
        "reservations": reservations,
        "registrations": registrations,
        "past_grades": past_grades,
        "outstanding_fees": outstanding_fees,
    }

    return render(request, "website/student_dashboard.html", context)


def validate_credit_limit(
    student: Student, section: Section, max_credits: int = 18
) -> bool:
    """Return ``True`` if adding ``section`` keeps the student under ``max_credits``."""
    reserved_credits = (
        Reservation.objects.filter(
            student=student, status__in=["requested", "validated"]
        ).aggregate(total=Sum("section__course__credit_hours"))["total"]
        or 0
    )

    return (reserved_credits + section.course.credit_hours) <= max_credits
