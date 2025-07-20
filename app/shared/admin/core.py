"""Admin utilities for shared components."""

from django.utils import timezone

from app.timetable.models.semester import Semester


def get_current_semester() -> Semester | None:
    """Return the semester covering today's date or the latest by start date."""
    today = timezone.now().date()
    sem = Semester.objects.filter(start_date__lte=today, end_date__gte=today).first()
    if sem:
        return sem
    return Semester.objects.order_by("-start_date").first()
