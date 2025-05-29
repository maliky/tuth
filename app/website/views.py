# app/website/views.py
from app.timetable.models.reservation import Reservation
from app.timetable.models.section import Section
from django.shortcuts import render

# import redirect


def landing_page(request):
    return render(request, "website/landing.html")


@login_required
def create_reservation(request, section_id):
    student = request.user.profile.studentprofile
    section = get_object_or_404(Section, id=section_id)

    reservation, created = Reservation.objects.get_or_create(
        student=student,
        section=section,
        defaults={"status": Reservation.Status.REQUESTED},
    )

    if not created:
        messages.info(request, "You have already reserved this section.")
        return redirect("student_dashboard")

    if not section.has_available_seats():
        reservation.delete()
        messages.error(request, "Section is full.")
        return redirect("student_dashboard")

    if not validate_credit_limit(student, section):
        reservation.delete()
        messages.error(request, "Exceeded credit-hour limit.")
        return redirect("student_dashboard")

    messages.success(request, "Reservation successful.")
    return redirect("student_dashboard")


def validate_credit_limit(student, section, max_credits=18):
    reserved_credits = (
        Reservation.objects.filter(
            student=student, status__in=["requested", "validated"]
        ).aggregate(total=models.Sum("section__course__credit_hours"))["total"]
        or 0
    )

    return (reserved_credits + section.course.credit_hours) <= max_credits
