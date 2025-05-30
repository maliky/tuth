from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render

from app.shared.constants.finance import StatusReservation
from app.timetable.models.reservation import Reservation
from app.timetable.models.section import Section


def landing_page(request):
    return render(request, "website/landing.html")


@login_required
def create_reservation(request, section_id):
    student = request.user.profile.studentprofile
    section = get_object_or_404(Section, id=section_id)
    reservation, created = Reservation.objects.get_or_create(
        student=student,
        section=section,
        defaults={"status": StatusReservation.REQUESTED},
    )

    if not created:
        messages.info(request, "You have already reserved this section.")
        return redirect("student_dashboard")

    try:
        reservation.full_clean()
    except ValidationError as err:
        reservation.delete()
        messages.error(request, str(err))
        return redirect("student_dashboard")

    if not validate_credit_limit(student, section):
        reservation.delete()
        messages.error(request, "Exceeded credit-hour limit.")
        return redirect("student_dashboard")

    messages.success(request, "Reservation successful.")
    return redirect("student_dashboard")


@login_required
def student_dashboard(request):
    """List reservations and handle creation via POST."""
    student = request.user.profile.studentprofile
    if request.method == "POST":
        section_id = request.POST.get("section_id")
        if section_id:
            return create_reservation(request, section_id)

    reservations = (
        Reservation.objects.filter(student=student)
        .select_related("section__course")
        .order_by("-date_requested")
    )
    return render(
        request,
        "website/reservations.html",
        {"reservations": reservations},
    )


def validate_credit_limit(student, section, max_credits=18):
    reserved_credits = (
        Reservation.objects.filter(
            student=student, status__in=["requested", "validated"]
        ).aggregate(total=models.Sum("section__course__credit_hours"))["total"]
        or 0
    )

    return (reserved_credits + section.course.credit_hours) <= max_credits
