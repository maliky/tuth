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


class StaffChoiceField(forms.ModelChoiceField):
    """ModelChoiceField that displays staff long names."""

    def label_from_instance(self, obj: Staff) -> str:
        return obj.long_name or str(obj)


class AmountDueFlt(admin.SimpleListFilter):
    """Filter invoices by remaining balance."""

    title = "Amount due"
    parameter_name = "balance"

    def lookups(self, request, model_admin):
        return (
            ("zero", "Zero balance"),
            ("low", "balance <= 60%"),
            ("mid", "60% < balance"),
            ("full", "Full balance"),
        )

    @staticmethod
    def _threshold(row: AmountDueRowT) -> Decimal:
        """Return the deposit threshold without instantiating deferred models."""
        initial_amount_due = row[2] or Decimal("0.00")
        if len(row) == 4:
            percent = (row[3] or Decimal("0.00")) / Decimal("100.00")
            return initial_amount_due * percent
        return initial_amount_due * Decimal("0.40")

    @staticmethod
    def _balance(row: AmountDueRowT) -> Decimal:
        """Return a non-null balance fallback for value rows."""
        return row[1] or row[2] or Decimal("0.00")

    @staticmethod
    def _value_fields(queryset) -> list[str]:
        """Return minimal fields needed for amount-due filtering."""
        fields = ["id", "balance", "initial_amount_due"]
        model_fields = {field.name for field in queryset.model._meta.fields}
        if "required_deposit_percent" in model_fields:
            fields.append("required_deposit_percent")
        return fields

    def queryset(self, request, queryset):
        value = self.value()
        if value == "zero":
            return queryset.filter(balance=0)
        if value == "full":
            return queryset.filter(balance=F("initial_amount_due"))

        if value not in {"low", "mid"}:
            return queryset

        invoice_ids: list[int] = []
        # Use values instead of model instances; .only() conflicts with admin facets.
        for row in queryset.values_list(*self._value_fields(queryset)):
            amount_row = row
            threshold = self._threshold(amount_row)
            balance = self._balance(amount_row)

            if value == "low" and balance <= threshold:
                invoice_ids.append(amount_row[0])
            if value == "mid" and threshold < balance:
                invoice_ids.append(amount_row[0])

        return queryset.filter(pk__in=invoice_ids)


@admin.register(CrsInvoice)
class CrsInvoiceAdmin(
    ScopedAutocompleteAdminMixin,
    SimpleHistoryAdmin,
    ImportExportModelAdmin,
    GuardedModelAdmin,
):
    """Admin settings for course invoices."""

    resource_class = InvoiceResource
    list_display = (
        "std_label",
        "curriculum_course",
        "sem_label",
        "student_semester_invoice",
        "balance",
        "payments_link",
        "created_at",
        # "recorded_by_name",
    )
    list_filter = (SemFltAC, AmountDueFlt)
    list_select_related = (
        "student",
        "student__user",
        "semester",
        "curriculum_course",
        "student_semester_invoice",
        # "recorded_by",
    )
    readonly_fields = ("created_at",)
    inlines = ()
    search_fields = (
        "curriculum_course__course__short_code",
        "curriculum_course__course__code",
        "curriculum_course__course__title",
        "student__student_id",
        "student__long_name",
        "student__user__first_name",
        "student__user__last_name",
        "student__user__username",
        "semester__academic_year__code",
    )
    # Enable curriculum course autocomplete so short_code searches work in add view.
    autocomplete_fields = ("student", "recorded_by", "curriculum_course")
    actions = ("create_payment_action",)

    def get_queryset(self, request):
        """Annotate payment counts for list display."""
        queryset = super().get_queryset(request)
        return queryset.annotate(
            payments_count=Count("student_semester_invoice__payments", distinct=True)
        )

    @admin.display(description="Payments")
    def payments_link(self, obj: CrsInvoice) -> str:
        """Return a clickable payment count for the invoice."""
        count = getattr(obj, "payments_count", 0)
        parent_invoice_id = obj.student_semester_invoice_id
        if not count or parent_invoice_id is None:
            return "0"
        base_url = reverse("admin:finance_payment_changelist")
        query = urlencode({"student_semester_invoice__id__exact": parent_invoice_id})
        return format_html('<a href="{}?{}">{}</a>', base_url, query, count)

    @admin.display(description="Student")
    def std_label(self, obj: CrsInvoice) -> str:
        """Return the student name and ID for display."""
        student = obj.student
        name = student.long_name or student.user.get_full_name() or student.student_id
        student_id = student.student_id or "Pending ID"
        return f"{name} ({student_id})"

    @admin.display(description="Semester")
    def sem_label(self, obj: CrsInvoice) -> str:
        """Return the invoice semester label."""
        return str(obj.semester)

    # @admin.display(description="Recorded by")
    # def recorded_by_name(self, obj: Invoice) -> str:
    #     """Return the staff long name for display."""
    #     recorded_by = obj.recorded_by
    #     if recorded_by is not None:
    #         return recorded_by.long_name or str(recorded_by)
    #     return "-"

    @admin.action(description="Create pending payments")
    def create_payment_action(self, request, queryset):
        """Create pending payments for selected invoices."""
        staff = self._resolve_recorded_by_staff(request)
        summary = create_pending_payments(queryset, recorded_by=staff)
        created = summary.get("created", 0)
        skipped_existing = summary.get("skipped_existing", 0)
        skipped_closed = summary.get("skipped_closed", 0)
        if created:
            messages.success(
                request,
                f"Created {created} pending payment(s) with full amounts.",
            )
        if skipped_existing:
            messages.info(
                request,
                f"Skipped {skipped_existing} invoice(s) with pending payments.",
            )
        if skipped_closed:
            messages.warning(
                request,
                f"Skipped {skipped_closed} invoice(s) with no balance due.",
            )

    def _get_open_regio_sem(self, request) -> Optional[Semester]:
        """Return the open registration semester, if available."""
        # It's not clear what we have in request and where _open_registration..
        # is coming from.
        if getattr(request, "_open_registration_semester_loaded", False):
            return getattr(request, "_open_regio_sem", None)

        semester, error_message = Semester.regio_open_sem()
        if error_message:
            messages.error(request, error_message)
        request._open_regio_sem = semester
        request._open_registration_semester_loaded = True

        return semester

    def _resolve_recorded_by_staff(self, request) -> Optional[Staff]:
        """Return the staff profile tied to the request user."""
        if getattr(request, "_recorded_by_staff_loaded", False):
            return getattr(request, "_recorded_by_staff", None)

        staff = getattr(request.user, "staff", None)
        if staff is None and request.user.is_superuser:
            messages.warning(
                request,
                "Superusers without staff profiles must select Recorded by manually.",
            )

        request._recorded_by_staff = staff
        request._recorded_by_staff_loaded = True
        return staff

    def get_changeform_initial_data(self, request):
        """Set default semester/recorded_by values for invoice creation."""
        initial = super().get_changeform_initial_data(request)
        open_semester = self._get_open_regio_sem(request)
        if open_semester and "semester" not in initial:
            initial["semester"] = str(open_semester.pk)
        staff = self._resolve_recorded_by_staff(request)
        if staff and "recorded_by" not in initial:
            initial["recorded_by"] = str(staff.pk)
        return initial

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Customize foreign key fields for defaulting and scoping."""
        if db_field.name == "curriculum_course":
            open_semester = self._get_open_regio_sem(request)
            # Only allow curriculum courses with sections in the open semester.
            if open_semester:
                kwargs["queryset"] = CurriCrs.objects.filter(
                    sections__semester=open_semester
                ).distinct()
            else:
                kwargs["queryset"] = CurriCrs.objects.none()

        if db_field.name == "recorded_by":
            kwargs["form_class"] = StaffChoiceField

        # Set the field before applying defaults to avoid using an unset value.
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if field is None:
            return field

        if db_field.name == "semester":
            open_semester = self._get_open_regio_sem(request)
            if open_semester and isinstance(field, forms.ModelChoiceField):
                field.initial = open_semester.pk

        if db_field.name == "recorded_by":
            # > TODO: handle superusers without staff profiles.
            # Superusers without staff profiles must select a staff entry manually.
            staff = self._resolve_recorded_by_staff(request)
            if staff and isinstance(field, forms.ModelChoiceField):
                field.initial = staff.pk

        return field

    def save_model(self, request, obj, form, change):
        """Persist defaults for recorded_by and semester on save."""
        if not obj.recorded_by_id:
            staff = self._resolve_recorded_by_staff(request)
            if staff:
                obj.recorded_by = staff
        if not obj.semester_id:
            open_semester = self._get_open_regio_sem(request)
            if open_semester:
                obj.semester = open_semester
        super().save_model(request, obj, form, change)


@admin.register(StdSemesterInvoice)
class StdSemInvoiceAdmin(
    ScopedAutocompleteAdminMixin,
    SimpleHistoryAdmin,
    GuardedModelAdmin,
):
    """Admin settings for parent student-semester invoices."""

    list_display = (
        "student",
        "semester",
        "course_tuition_payer",
        "fee_payer",
        "required_deposit_percent",
        "required_deposit_amount",
        "initial_amount_due",
        "balance",
        "status",
        "updated_at",
    )
    list_filter = (SemFltAC, AmountDueFlt)
    search_fields = (
        "student__student_id",
        "student__long_name",
        "student__user__first_name",
        "student__user__last_name",
        "semester__academic_year__code",
    )
    list_select_related = ("student", "semester", "status")
    autocomplete_fields = ("student", "semester", "fee_stacks")
    inlines = (StdSemCrsInvoiceIL, InvoicePaymentIL)
    readonly_fields = ("created_at", "updated_at")

    def get_inline_instances(self, request, obj=None) -> list[InlineModelAdmin]:
        """Skip empty invoice-detail inlines while the parent invoice is unsaved."""
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)

    def save_model(self, request, obj, form, change):
        """Keep parent totals aligned after manual admin edits."""
        super().save_model(request, obj, form, change)
        obj.refresh_totals_from_sources(save_model=True)

    def save_related(self, request, form, formsets, change):
        """Refresh totals after fee-stack and payment inline changes."""
        super().save_related(request, form, formsets, change)
        form.instance.refresh_totals_from_sources(save_model=True)


__all__ = ["AmountDueFlt", "CrsInvoiceAdmin", "StaffChoiceField", "StdSemInvoiceAdmin"]
