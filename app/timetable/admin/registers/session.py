"""Session admin module."""

from app.timetable.admin.inlines import SessionInline
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.timetable.admin.resources.session import ScheduleResource, SessionResource
from app.timetable.models.schedule import Schedule
from app.timetable.models.session import Session


@admin.register(Session)
class SessionAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin configuration for Session.

    list_display exposes schedule, room and related section details. The
    list can be filtered by weekday or space.
    """

    resource_class = SessionResource
    list_display = (
        "schedule",
        "room",
        "section__program__course",
        "section__semester",
        "section__number",
        "section__faculty",
    )
    # need to be 'real' fieds not FK,
    search_fields = (
        "room__code",
        "section__program__course__code",
        "section__program__course__title",
        "section__faculty__staff_profile__user__first_name",
        "section__faculty__staff_profile__user__last_name",
    )
    list_filter = ("schedule__weekday", "room__space")
    # useful when creating new schedules
    autocomplete_fields = (
        "section",
        "schedule",
        "room",
    )


@admin.register(Schedule)
class ScheduleAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for :class:~app.timetable.models.Schedule.

    Allows filtering by weekday and supports import/export operations.
    """

    resource_class = ScheduleResource
    list_display = ("weekday", "start_time", "end_time")
    list_filter = ("weekday",)
    search_fields = ("weekday",)
    inlines = [SessionInline]
