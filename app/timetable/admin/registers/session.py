"""Session admin module."""

from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.timetable.admin.resources.session import ScheduleResource, SessionResource
from app.timetable.models.session import Schedule, Session


@admin.register(Session)
class SessionAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin configuration for :class:`Session`."""

    resource_class = SessionResource
    list_display = (
        "schedule",
        "room",
        "section__course",
        "section__semester",
        "section__number",
        "section__faculty",
    )
    search_fields = ("section",)
    # is it possible to filter per space?
    list_filter = ("schedule__weekday", "room__space")
    # if already in filter remove from here
    # autocomplete_fields = ("room",)


@admin.register(Schedule)
class ScheduleAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin for Schedule"""

    resource_class = ScheduleResource
    list_display = ("weekday", "start_time", "end_time")
    list_filter = ("weekday",)
    search_fields = ("weekday",)
