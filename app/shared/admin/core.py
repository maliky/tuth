"""Admin utilities for shared components."""

from django.contrib import admin
from django.utils import timezone
from simple_history.admin import SimpleHistoryAdmin

from app.registry.models import CreditHour
from app.timetable.models.semester import Semester


def get_current_semester() -> Semester | None:
    """Return the latest semester whose start date is on or before today."""
    today = timezone.now().date()
    sem = Semester.objects.filter(start_date__lte=today).order_by("-start_date").first()
    if sem:
        return sem
    # Fall back to the earliest start when all semesters are in the future.
    return Semester.objects.order_by("start_date").first()


@admin.register(CreditHour)
class CreditHourAdmin(SimpleHistoryAdmin):
    """Lookup admin for CreditHour."""

    search_fields = ("code", "label")
    list_display = ("code", "label")
