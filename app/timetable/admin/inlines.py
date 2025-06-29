"""app.timetable.Inlines modules."""

from django.contrib import admin

from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.timetable.models.session import Session


class SemesterInline(admin.TabularInline):
    """Inline for managing Semester rows."""

    model = Semester
    extra = 0
    max_num = 3
    fields = ("number", "start_date", "end_date")
    ordering = ("start_date",)


class SessionInline(admin.TabularInline):
    """Inline editor for Session rows."""

    model = Session
    extra = 0
    fields = ("section", "room", "schedule", )
    autocomplete_fields = ("section", "room", "schedule", )


class SectionInline(admin.TabularInline):
    """Inline for creating Section rows."""

    model = Section
    extra = 0
    fields = (
        "semester",
        "number",
        "faculty",
        "start_date",
        "max_seats",
        "current_registrations",
    )
    readonly_fields = ("current_registrations",)
    ordering = ("-semester__start_date", "-number")


