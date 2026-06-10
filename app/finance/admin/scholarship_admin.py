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


@admin.register(Scholarship)
class ScholarshipAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin interface forScholarship.

    Autocomplete is enabled for donor and student foreign keys and key fields
    are displayed in the list view.
    """

    list_display = ("student", "donor", "amount", "start_date", "end_date")
    autocomplete_fields = ("donor", "student")


__all__ = ["ScholarshipAdmin"]
