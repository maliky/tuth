"""SecSession admin module."""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.timetable.admin.inlines import SecSessionIL
from app.timetable.admin.session_resources import ScheduleResource, SecSessionResource
from app.timetable.admin.filters import SecSessionFacultyFltAc
from app.timetable.models.schedule import Schedule
from app.timetable.models.session import SecSession


@admin.register(SecSession)
class SecSessionAdmin(SimpleHistoryAdmin, ImportExportModelAdmin, GuardedModelAdmin):
    """Admin configuration for SecSession.

    list_display exposes schedule, room and related section details. The
    list can be filtered by weekday or space.
    """

    resource_class = SecSessionResource
    list_display = (
        "schedule",
        "room",
        "section_curriculum_course_link",
        "section__semester",
        "section__number",
        "section_faculty_link",
    )
    # need to be 'real' fieds not FK,
    search_fields = (
        "room__code",
        "section__curriculum_course__course__code",
        "section__curriculum_course__course__title",
        "section__faculty__staff_profile__user__first_name",
        "section__faculty__staff_profile__user__last_name",
    )
    list_filter = ("schedule__weekday", "room__space", SecSessionFacultyFltAc)
    # useful when creating new schedules
    autocomplete_fields = (
        "section",
        "schedule",
        "room",
    )
    list_select_related = (
        "room",
        "schedule",
        "section__semester",
        "section__faculty",
        "section__curriculum_course",
    )

    @admin.display(description="Curriculum Course")
    def section_curriculum_course_link(self, obj):
        """Link to the curriculum course attached to the session section."""
        curriculum_course = obj.section.curriculum_course
        url = reverse("admin:academics_curricourse_change", args=[curriculum_course.pk])
        return format_html('<a href="{}">{}</a>', url, curriculum_course)

    @admin.display(description="Faculty")
    def section_faculty_link(self, obj):
        """Link to the faculty profile attached to the session section."""
        faculty = obj.section.faculty
        if not faculty:
            return "-"
        url = reverse("admin:people_faculty_change", args=[faculty.pk])
        return format_html('<a href="{}">{}</a>', url, faculty)


@admin.register(Schedule)
class ScheduleAdmin(SimpleHistoryAdmin, ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for :class:~app.timetable.models.Schedule.

    Allows filtering by weekday and supports import/export operations.
    """

    resource_class = ScheduleResource
    list_display = ("weekday", "start_time", "end_time")
    list_filter = ("weekday",)
    search_fields = ("weekday",)
    inlines = [SecSessionIL]
