"""Schedule admin module."""

from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.timetable.models.schedule import Schedule
from .resources import ScheduleResource


@admin.register(Schedule)
class ScheduleAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin configuration for :class:`Schedule`."""

    resource_class = ScheduleResource
    list_display = ("section", "weekday", "start_time", "end_time", "room")
    list_filter = ("weekday", "room")
    autocomplete_fields = ("section", "room")
