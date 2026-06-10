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


class FeeStackLineIL(admin.TabularInline):
    """Inline editor for fee lines in a fee stack."""

    model = FeeStackLine
    extra = 0
    show_change_link = True
    autocomplete_fields = ("fee_type", "payer", "effective_from_semester")
    fields = ("fee_type", "amount", "payer", "effective_from_semester")


class CrsFeeStackIL(admin.TabularInline):
    """Inline editor for attaching courses to a fee stack."""

    model = CrsFeeStack
    fk_name = "fee_stack"
    extra = 0
    autocomplete_fields = ("course",)
    fields = ("course",)
    ordering = ("course__short_code",)


@admin.register(FeeStack)
class FeeStackAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin settings for FeeStack."""

    list_display = (
        "name",
        "payer",
        "current_sem_total",
        "fee_line_count",
        "crs_count",
    )
    search_fields = ("name", "courses__short_code", "courses__code", "courses__title")
    inlines = [FeeStackLineIL, CrsFeeStackIL]
    _current_semester_cache: Optional[Semester] = None
    _current_semester_loaded = False

    def _resolved_current_sem(self) -> Optional[Semester]:
        """Return the current semester, or the latest one when none is active."""
        if self._current_semester_loaded:
            return self._current_semester_cache
        today = timezone.now().date()
        semester = (
            Semester.objects.filter(start_date__lte=today).order_by("-start_date").first()
        )
        if semester is None:
            semester = Semester.objects.order_by("-start_date").first()
        self._current_semester_cache = semester
        self._current_semester_loaded = True
        return semester

    def get_queryset(self, request):
        """Annotate sortable totals and counts for fee stack changelist."""
        queryset = super().get_queryset(request)
        semester = self._resolved_current_sem()
        cutoff_date = getattr(semester, "start_date", None)
        current_total_sql = """
            SELECT COALESCE(SUM(chosen.amount), 0.00)
            FROM (
                SELECT DISTINCT ON (fsl.fee_type_id) fsl.amount
                FROM finance_feestackline fsl
                LEFT JOIN timetable_semester sem
                    ON sem.id = fsl.effective_from_semester_id
                WHERE fsl.fee_stack_id = finance_feestack.id
                  AND (
                      %s::date IS NULL
                      OR fsl.effective_from_semester_id IS NULL
                      OR sem.start_date <= %s::date
                  )
                ORDER BY
                    fsl.fee_type_id,
                    CASE WHEN fsl.effective_from_semester_id IS NULL THEN 1 ELSE 0 END,
                    sem.start_date DESC NULLS LAST,
                    fsl.id DESC
            ) AS chosen
        """

        return queryset.annotate(
            annotated_fee_line_count=Count("fees", distinct=True),
            annotated_course_count=Count("courses", distinct=True),
            current_total_amount=Coalesce(
                RawSQL(
                    current_total_sql,
                    [cutoff_date, cutoff_date],
                    output_field=DecimalField(),
                ),
                Value(Decimal("0.00"), output_field=DecimalField()),
            ),
        )

    @admin.display(description="Fee lines", ordering="annotated_fee_line_count")
    def fee_line_count(self, obj: FeeStack) -> int:
        """Return the number of fee lines in the stack."""
        return int(getattr(obj, "annotated_fee_line_count", obj.fees.count()))

    @admin.display(description="Current total", ordering="current_total_amount")
    def current_sem_total(self, obj: FeeStack) -> str:
        """Return stack total resolved for the current semester context."""
        total = getattr(obj, "current_total_amount", None)
        if total is None:
            semester = self._resolved_current_sem()
            total = obj.total_amount_for_sem(semester)
        return f"{Decimal(total):.2f}"

    @admin.display(description="Crss", ordering="annotated_course_count")
    def crs_count(self, obj: FeeStack) -> int:
        """Return how many courses are linked to the stack."""
        return int(getattr(obj, "annotated_course_count", obj.courses.count()))


@admin.register(FeeStackLine)
class FeeStackLineAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin settings for FeeStackLine."""

    list_display = (
        "fee_stack",
        "fee_type",
        "amount",
        "payer",
        "effective_from_semester",
    )
    autocomplete_fields = ("fee_stack", "fee_type", "payer", "effective_from_semester")
    search_fields = ("fee_stack__name", "fee_type__code", "fee_type__label")
    list_filter = (
        FeeStackFltAC,
        FeeTypeFltAC,
        EffectiveSemesterFltAC,
    )


@admin.register(CrsFeeStack)
class CrsFeeStackAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin settings for CrsFeeStack."""

    list_display = ("course", "fee_stack")
    autocomplete_fields = ("course", "fee_stack")
    search_fields = (
        "course__short_code",
        "course__code",
        "course__title",
        "fee_stack__name",
    )


__all__ = [
    "CrsFeeStackAdmin",
    "CrsFeeStackIL",
    "FeeStackAdmin",
    "FeeStackLineAdmin",
    "FeeStackLineIL",
]
