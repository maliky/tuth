"""app.timetable.Inlines modules."""

from app.timetable.models.reservation import Reservation
from app.timetable.models.session import Session
from django.contrib import admin

from app.timetable.models import Section, Semester


class SemesterInline(admin.TabularInline):
    """Inline for managing :class:~app.timetable.models.Semester rows."""

    model = Semester
    extra = 0
    max_num = 3
    fields = ("number", "start_date", "end_date")
    ordering = ("start_date",)


class SessionInline(admin.TabularInline):
    """Inline editor for :class:~app.timetable.models.Session."""

    model = Session
    extra = 0
    fields = ("room", "schedule")
    autocomplete_fields = ("room", "schedule")


class SectionInline(admin.TabularInline):
    """Inline for creating :class:~app.timetable.models.Section rows."""

    model = Section
    extra = 0
    fields = (
        "semester",
        "course",
        "number",
        "faculty",
        "start_date",
        "max_seats",
        "current_registrations",
    )
    readonly_fields = ("current_registrations",)
    ordering = ("semester__start_date", "number")


class ReservationInline(admin.TabularInline):
    """Inline for :class:~app.timetable.models.Reservation records.

    Shows each reservation with status and credit hour snapshot.
    """

    model = Reservation
    extra = 0
    fields = (
        "student",
        "section",
        "status",
        "date_requested",
        "credit_hours",
    )
    readonly_fields = (
        "date_requested",
        "credit_hours",
    )
