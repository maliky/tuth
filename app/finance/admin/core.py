"""Core module."""

from django.contrib import admin

from app.finance.models.payment import Payment
from app.finance.models.payment_history import PaymentHistory
from app.finance.models.scholarship import Scholarship


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin settings for :class:`~app.finance.models.Payment`."""

    list_display = ("reservation", "amount", "method", "recorded_by", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Scholarship)
class ScholarshipAdmin(admin.ModelAdmin):
    """Admin interface for :class:`~app.finance.models.Scholarship`."""

    list_display = ("student", "donor", "amount", "start_date", "end_date")
    autocomplete_fields = ("donor", "student")


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    """Admin settings for :class:`~app.finance.models.PaymentHistory`."""

    list_display = (
        "financial_record",
        "amount",
        "method",
        "recorded_by",
        "payment_date",
    )
    readonly_fields = ("payment_date",)
