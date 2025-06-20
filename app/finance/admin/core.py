"""Core module."""

from django.contrib import admin

from app.finance.models.payment import Payment

from app.finance.models.payment_history import PaymentHistory
from app.finance.models.scholarship import Scholarship


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin settings for :class:~app.finance.models.Payment.

    Uses list_display to show reservation, method and recorder and marks
    created_at as read-only.
    """

    # Use Payment.__str__ for readability in list views
    list_display = ("__str__", "reservation", "method", "recorded_by")
    readonly_fields = ("created_at",)


@admin.register(Scholarship)
class ScholarshipAdmin(admin.ModelAdmin):
    """Admin interface for :class:~app.finance.models.Scholarship.

    Autocomplete is enabled for donor and student foreign keys and key fields
    are displayed in the list view.
    """

    list_display = ("student", "donor", "amount", "start_date", "end_date")
    autocomplete_fields = ("donor", "student")


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    """Admin interface for :class:~app.finance.models.PaymentHistory.

    Shows a summary string along with the record, payment method and user.
    Payment date is shown but cannot be edited.
    """

    # Shows summary string plus related info
    list_display = ("__str__", "financial_record", "method", "recorded_by")
    readonly_fields = ("payment_date",)
