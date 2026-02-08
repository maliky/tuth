"""Core module."""

from decimal import Decimal
from typing import Optional

from app.finance.models.fee_stack import CourseFeeStack, FeeStack, FeeStackLine
from app.finance.models.status_types_methods import (
    FeeType,
    Payer,
    PaymentMethod,
    PaymentStatus,
    InvoiceStatus,
)
from django import forms
from django.contrib import admin, messages
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

from app.academics.models.curriculum_course import CurriculumCourse
from app.finance.admin.resources import InvoiceResource, PaymentResource
from app.finance.admin.filters import (
    EffectiveSemesterFilterAC,
    FeeStackFilterAC,
    FeeTypeFilterAC,
)
from app.finance.admin.inlines import (
    InvoicePaymentInline,
    StudentSemesterCourseInvoiceInline,
)
from app.finance.models.payment import Payment
from app.finance.models.invoice import CourseInvoice, StudentSemesterInvoice
from app.finance.models.scholarship import Scholarship
from app.finance.utils import create_pending_payments
from app.people.models.staffs import Staff
from app.shared.admin.mixins import ScopedAutocompleteAdminMixin
from app.timetable.admin.filters import SemesterFilterAC
from app.timetable.models.semester import Semester


class StaffChoiceField(forms.ModelChoiceField):
    """ModelChoiceField that displays staff long names."""

    def label_from_instance(self, obj: Staff) -> str:
        return obj.long_name or str(obj)


class AmountDueFilter(admin.SimpleListFilter):
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

    def queryset(self, request, queryset):
        value = self.value()
        if value == "zero":
            return queryset.filter(balance=0)
        if value == "full":
            return queryset.filter(balance=F("initial_amount_due"))

        if value not in {"low", "mid"}:
            return queryset

        invoice_ids: list[int] = []
        # Limit columns since we only need balances and initial totals.
        for invoice in queryset.only("id", "balance", "initial_amount_due"):
            threshold = invoice.initial_forty_percent_due()

            if value == "low" and invoice.balance <= threshold:
                invoice_ids.append(invoice.pk)
            if value == "mid" and threshold < invoice.balance:
                invoice_ids.append(invoice.pk)

        return queryset.filter(pk__in=invoice_ids)


@admin.register(CourseInvoice)
class CourseInvoiceAdmin(
    ScopedAutocompleteAdminMixin,
    SimpleHistoryAdmin,
    ImportExportModelAdmin,
    GuardedModelAdmin,
):
    """Admin settings for course invoices."""

    resource_class = InvoiceResource
    list_display = (
        "student_label",
        "curriculum_course",
        "semester_label",
        "student_semester_invoice",
        "balance",
        "payments_link",
        "created_at",
        # "recorded_by_name",
    )
    list_filter = (SemesterFilterAC, AmountDueFilter)
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
    def payments_link(self, obj: CourseInvoice) -> str:
        """Return a clickable payment count for the invoice."""
        count = getattr(obj, "payments_count", 0)
        parent_invoice_id = obj.student_semester_invoice_id
        if not count or parent_invoice_id is None:
            return "0"
        base_url = reverse("admin:finance_payment_changelist")
        query = urlencode({"student_semester_invoice__id__exact": parent_invoice_id})
        return format_html('<a href="{}?{}">{}</a>', base_url, query, count)

    @admin.display(description="Student")
    def student_label(self, obj: CourseInvoice) -> str:
        """Return the student name and ID for display."""
        student = obj.student
        name = student.long_name or student.user.get_full_name() or student.student_id
        student_id = student.student_id or "Pending ID"
        return f"{name} ({student_id})"

    @admin.display(description="Semester")
    def semester_label(self, obj: CourseInvoice) -> str:
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

    def _get_open_registration_semester(self, request) -> Optional[Semester]:
        """Return the open registration semester, if available."""
        # It's not clear what we have in request and where _open_registration..
        # is coming from.
        if getattr(request, "_open_registration_semester_loaded", False):
            return getattr(request, "_open_registration_semester", None)

        semester, error_message = Semester.registration_open_semester()
        if error_message:
            messages.error(request, error_message)
        request._open_registration_semester = semester
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
        open_semester = self._get_open_registration_semester(request)
        if open_semester and "semester" not in initial:
            initial["semester"] = str(open_semester.pk)
        staff = self._resolve_recorded_by_staff(request)
        if staff and "recorded_by" not in initial:
            initial["recorded_by"] = str(staff.pk)
        return initial

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Customize foreign key fields for defaulting and scoping."""
        if db_field.name == "curriculum_course":
            open_semester = self._get_open_registration_semester(request)
            # Only allow curriculum courses with sections in the open semester.
            if open_semester:
                kwargs["queryset"] = CurriculumCourse.objects.filter(
                    sections__semester=open_semester
                ).distinct()
            else:
                kwargs["queryset"] = CurriculumCourse.objects.none()

        if db_field.name == "recorded_by":
            kwargs["form_class"] = StaffChoiceField

        # Set the field before applying defaults to avoid using an unset value.
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if field is None:
            return field

        if db_field.name == "semester":
            open_semester = self._get_open_registration_semester(request)
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
            open_semester = self._get_open_registration_semester(request)
            if open_semester:
                obj.semester = open_semester
        super().save_model(request, obj, form, change)


@admin.register(StudentSemesterInvoice)
class StudentSemesterInvoiceAdmin(
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
    list_filter = (SemesterFilterAC, AmountDueFilter)
    search_fields = (
        "student__student_id",
        "student__long_name",
        "student__user__first_name",
        "student__user__last_name",
        "semester__academic_year__code",
    )
    list_select_related = ("student", "semester", "status")
    autocomplete_fields = ("student", "semester", "fee_stacks")
    inlines = (StudentSemesterCourseInvoiceInline, InvoicePaymentInline)
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        """Keep parent totals aligned after manual admin edits."""
        super().save_model(request, obj, form, change)
        obj.refresh_totals_from_sources(save_model=True)

    def save_related(self, request, form, formsets, change):
        """Refresh totals after fee-stack and payment inline changes."""
        super().save_related(request, form, formsets, change)
        form.instance.refresh_totals_from_sources(save_model=True)


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
    list_filter = (SemesterFilterAC,)
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


@admin.register(Scholarship)
class ScholarshipAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin interface forScholarship.

    Autocomplete is enabled for donor and student foreign keys and key fields
    are displayed in the list view.
    """

    list_display = ("student", "donor", "amount", "start_date", "end_date")
    autocomplete_fields = ("donor", "student")


class FeeStackLineInline(admin.TabularInline):
    """Inline editor for fee lines in a fee stack."""

    model = FeeStackLine
    extra = 0
    show_change_link = True
    autocomplete_fields = ("fee_type", "payer", "effective_from_semester")
    fields = ("fee_type", "amount", "payer", "effective_from_semester")


class CourseFeeStackInline(admin.TabularInline):
    """Inline editor for attaching courses to a fee stack."""

    model = CourseFeeStack
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
        "current_semester_total",
        "fee_line_count",
        "course_count",
    )
    search_fields = ("name", "courses__short_code", "courses__code", "courses__title")
    inlines = [FeeStackLineInline, CourseFeeStackInline]
    _current_semester_cache: Optional[Semester] = None
    _current_semester_loaded = False

    def _resolved_current_semester(self) -> Optional[Semester]:
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
        semester = self._resolved_current_semester()
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
    def current_semester_total(self, obj: FeeStack) -> str:
        """Return stack total resolved for the current semester context."""
        total = getattr(obj, "current_total_amount", None)
        if total is None:
            semester = self._resolved_current_semester()
            total = obj.total_amount_for_semester(semester)
        return f"{Decimal(total):.2f}"

    @admin.display(description="Courses", ordering="annotated_course_count")
    def course_count(self, obj: FeeStack) -> int:
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
        FeeStackFilterAC,
        FeeTypeFilterAC,
        EffectiveSemesterFilterAC,
    )


@admin.register(CourseFeeStack)
class CourseFeeStackAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin settings for CourseFeeStack."""

    list_display = ("course", "fee_stack")
    autocomplete_fields = ("course", "fee_stack")
    search_fields = (
        "course__short_code",
        "course__code",
        "course__title",
        "fee_stack__name",
    )
