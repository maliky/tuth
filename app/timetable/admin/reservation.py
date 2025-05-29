from django.contrib import admin
from .models import Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("student", "section", "status", "date_requested", "date_validated")
    list_filter = ("status",)
    actions = ["validate_reservations"]

    @admin.action(description="Validate selected reservations")
    def validate_reservations(self, request, queryset):
        for reservation in queryset:
            try:
                reservation.validate()
            except ValueError as e:
                self.message_user(request, str(e), level="error")
