from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render

from app.shared.constants.choices import StatusReservation
from app.timetable.models.reservation import Reservation
from app.timetable.models.section import Section
from app.registry.models import Registration
from app.finance.models import FinancialRecord


def landing_page(request):
    return render(request, "website/landing.html")


@login_required
def create_reservation(request, section_id):
    student = request.user.profile.studentprofile
    section = get_object_or_404(Section, id=section_id)

    # Do not create duplicate reservations
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
    student = request.user.profile.studentprofile

    if request.method == "POST":
        section_id = request.POST.get("section_id")
        if section_id:
            return create_reservation(request, section_id)

    available_sections = (
        Section.objects.annotate(seats_left=F("max_seats") - F("current_registrations"))
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
    outstanding_fees = 0
    if financial_record:
        outstanding_fees = financial_record.total_due - financial_record.total_paid

    past_grades = []  # Placeholder until grading is implemented

    context = {
        "available_sections": available_sections,
        "reservations": reservations,
        "registrations": registrations,
        "past_grades": past_grades,
        "outstanding_fees": outstanding_fees,
    }

    return render(request, "website/student_dashboard.html", context)


def validate_credit_limit(student, section, max_credits=18):
    reserved_credits = (
        Reservation.objects.filter(
            student=student, status__in=["requested", "validated"]
        ).aggregate(total=models.Sum("section__course__credit_hours"))["total"]
        or 0
    )

    return (reserved_credits + section.course.credit_hours) <= max_credits
