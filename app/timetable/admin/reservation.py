"""Reservation module."""

from __future__ import annotations

from django.contrib import admin

from .models import Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    """Admin interface for :class:`~app.timetable.models.Reservation`."""
    list_display = (
        "student",
        "section",
        "status",
        "fee_total",
        "date_requested",
        "date_validated",
    )
    list_filter = ("status",)
    actions = ["validate_reservation", "mark_paid_action"]

    @admin.action(description="Mark selected reservations as paid")
    def validate_reservation(self, request, queryset):
        for reservation in queryset:
            try:
                reservation.validate()
            except ValueError as e:
                self.message_user(request, str(e), level="error")

    @admin.action(description="Mark selected reservations paid")
    def mark_paid_action(self, request, queryset):
        for reservation in queryset:
            reservation.mark_paid(request.user)
