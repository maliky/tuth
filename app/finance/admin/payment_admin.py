"""Core module."""

from decimal import Decimal
from typing import Optional, TypeAlias

from app.finance.models.fee_stack import CrsFeeStack, FeeStack, FeeStackLine
from app.finance.models.status_types_methods import (
    FeeType,
    Payer,
    PaymentMethod,
    PaymentStatus,
    InvoiceStatus,
)
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.options import InlineModelAdmin
from django.db.models import (
    Count,
    DecimalField,
    F,
    Value,
)
from django.db.models.expressions import RawSQL
from django.urls import reverse
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils import timezone
from django.db.models.functions import Coalesce
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.academics.models.curriculum_course import CurriCrs
from app.finance.admin.resources import InvoiceResource, PaymentResource
from app.finance.admin.filters import (
    EffectiveSemesterFltAC,
    FeeStackFltAC,
    FeeTypeFltAC,
)
from app.finance.admin.inlines import (
    InvoicePaymentIL,
    StdSemCrsInvoiceIL,
)
from app.finance.models.payment import Payment
from app.finance.models.invoice import CrsInvoice, StdSemesterInvoice
from app.finance.models.scholarship import Scholarship
from app.finance.utils import create_pending_payments
from app.people.models.staffs import Staff
from app.shared.admin.mixins import ScopedAutocompleteAdminMixin
from app.timetable.admin.filters import SemFltAC
from app.timetable.models.semester import Semester

AmountDueRowT: TypeAlias = (
    tuple[int, Decimal | None, Decimal | None]
    | tuple[int, Decimal | None, Decimal | None, Decimal | None]
)


@admin.register(PaymentStatus, InvoiceStatus, FeeType, PaymentMethod, Payer)
class LookupAdmin(admin.ModelAdmin):
    """Basic admin for finance lookup tables."""

    search_fields = ("code", "label")
    list_display = ("label",)


@admin.register(Payment)
class PaymentAdmin(
    ScopedAutocompleteAdminMixin,
    SimpleHistoryAdmin,
    ImportExportModelAdmin,
    GuardedModelAdmin,
):
    """Admin interface for :class:`~app.finance.models.Payment`."""

    resource_class = PaymentResource
    list_display = (
        "student_semester_invoice",
        "payer",
        "amount_paid",
        "payment_method",
        "status",
        "recorded_by",
    )
    autocomplete_fields = (
        "payment_method",
        "student_semester_invoice",
        "status",
        "payer",
    )
    exclude = ("recorded_by",)
    list_filter = (SemFltAC,)
    list_select_related = (
        "student_semester_invoice",
        "student_semester_invoice__semester",
        "student_semester_invoice__student",
        "payer",
        "payment_method",
        "status",
    )

    def save_model(self, request, obj, form, change):
        """Set recorded_by from the logged-in staff profile."""
        if not obj.recorded_by_id:
            staff = getattr(request.user, "staff", None)
            if staff is None and request.user.is_superuser:
                messages.warning(
                    request,
                    "Superusers without staff profiles must select Recorded by manually.",
                )
            if staff:
                obj.recorded_by = staff
        super().save_model(request, obj, form, change)


__all__ = ["LookupAdmin", "PaymentAdmin"]
