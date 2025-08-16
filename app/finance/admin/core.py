"""Core module."""

from app.finance.choices import FeeType, PaymentMethod, ClearanceStatus
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.finance.models.financial_record import FinancialRecord
from app.finance.models.payment import Payment
from app.finance.models.payment_history import PaymentHistory
from app.finance.models.scholarship import Scholarship
from app.timetable.admin.filters import SemesterFilter


@admin.register(Payment)
class PaymentAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin settings for Payment."""

    list_display = ("__str__", "method", "recorded_by")
    list_filter = (SemesterFilter,)
    readonly_fields = ("created_at",)


@admin.register(FinancialRecord)
class FinancialRecordAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin interface for :class:`~app.finance.models.FinancialRecord`."""

    list_display = ("student", "total_due", "total_paid", "clearance_status")
    autocomplete_fields = ("student", "verified_by")


@admin.register(Scholarship)
class ScholarshipAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin interface forScholarship.

    Autocomplete is enabled for donor and student foreign keys and key fields
    are displayed in the list view.
    """

    list_display = ("student", "donor", "amount", "start_date", "end_date")
    autocomplete_fields = ("donor", "student")


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin interface for :class:~app.finance.models.PaymentHistory.

    Shows a summary string along with the record, payment method and user.
    Payment date is shown but cannot be edited.
    """

    # Shows summary string plus related info
    list_display = ("__str__", "financial_record", "method", "recorded_by")
    list_filter = (SemesterFilter,)
    readonly_fields = ("payment_date",)


@admin.register(ClearanceStatus, FeeType, PaymentMethod)
class LookupAdmin(admin.ModelAdmin):
    """Basic admin for finance lookup tables."""

    search_fields = ("code", "label")
