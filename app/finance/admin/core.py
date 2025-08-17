"""Core module."""

from app.finance.models.payment import FeeType, PaymentMethod, ClearanceStatus
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.finance.models.payment import Payment
from app.finance.models.invoice import Invoice
from app.finance.models.scholarship import Scholarship
from app.timetable.admin.filters import SemesterFilter


@admin.register(Invoice)
class InvoiceAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin settings for Payment."""

    list_display = ("__str__", "recorded_by")
    list_filter = (SemesterFilter,)
    readonly_fields = ("created_at",)
    search_fields = ("program", "student", "semester")


@admin.register(Payment)
class PaymentAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin interface for :class:`~app.finance.models.Payment`."""

    list_display = ("invoice", "amount_paid", "payment_method", "status", "recorded_by")
    autocomplete_fields = ("recorded_by", "payment_method", "invoice", "status")


@admin.register(Scholarship)
class ScholarshipAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin interface forScholarship.

    Autocomplete is enabled for donor and student foreign keys and key fields
    are displayed in the list view.
    """

    list_display = ("student", "donor", "amount", "start_date", "end_date")
    autocomplete_fields = ("donor", "student")


@admin.register(ClearanceStatus, FeeType, PaymentMethod)
class LookupAdmin(admin.ModelAdmin):
    """Basic admin for finance lookup tables."""

    search_fields = ("code", "label")
