"""Core module."""

from django.contrib import admin

from app.finance.models import Payment, PaymentHistory, Scholarship


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin settings for :class:`~app.finance.models.Payment`."""

    # Use Payment.__str__ for readability in list views
    list_display = ("__str__", "reservation", "method", "recorded_by")
    readonly_fields = ("created_at",)


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    """Admin interface for :class:`~app.finance.models.PaymentHistory`."""

    # Shows summary string plus related info
    list_display = ("__str__", "financial_record", "method", "recorded_by")


@admin.register(Scholarship)
class ScholarshipAdmin(admin.ModelAdmin):
    """Admin interface for :class:`~app.finance.models.Scholarship`."""

    list_display = ("student", "donor", "amount", "start_date", "end_date")
    autocomplete_fields = ("donor", "student")
