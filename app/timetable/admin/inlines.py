"""app.timetable.Inlines modules."""

from app.timetable.models.reservation import Reservation
from app.timetable.models.session import Session
from django.contrib import admin

from app.timetable.models import Section, Semester


class SemesterInline(admin.TabularInline):
    model = Semester
    extra = 0
    max_num = 3
    fields = ("number", "start_date", "end_date")
    ordering = ("start_date",)


class SessionInline(admin.TabularInline):
    model = Session
    extra = 0
    fields = ("room", "schedule")
    autocomplete_fields = ("room", "schedule")


class SectionInline(admin.TabularInline):
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
    """Display reservations inline with credit hours snapshot."""

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
