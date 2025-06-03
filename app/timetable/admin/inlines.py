"""Inlines module."""

from app.timetable.models.reservation import Reservation
from django.contrib import admin

from app.timetable.models import Section, Semester


class SemesterInline(admin.TabularInline):
    model = Semester
    extra = 0
    max_num = 3
    fields = ("number", "start_date", "end_date")
    ordering = ("start_date",)


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0
    fields = ("course", "number", "semester", "faculty", "room", "max_seats")
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
