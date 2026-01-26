"""Admin utilities for shared components."""

from django.contrib import admin
from django.utils import timezone
from simple_history.admin import SimpleHistoryAdmin

from app.registry.models import CreditHour
from app.timetable.models.semester import Semester


@admin.register(CreditHour)
class CreditHourAdmin(SimpleHistoryAdmin):
    """Lookup admin for CreditHour."""

    search_fields = ("code", "label")
    list_display = ("code", "label")
