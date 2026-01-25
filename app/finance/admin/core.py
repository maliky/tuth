"""Core module."""

from typing import Optional

from app.finance.models.payment import FeeType, PaymentMethod, ClearanceStatus, SectionFee
from django import forms
from django.contrib import admin, messages
from django.db.models import Count, F
from django.urls import reverse
from django.utils.html import format_html
from django.utils.http import urlencode
from guardian.admin import GuardedModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.academics.models.course import CurriculumCourse
from app.finance.admin.inlines import InvoicePaymentInline
from app.finance.models.payment import Payment
from app.finance.models.invoice import Invoice
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


@admin.register(SectionFee)
class SectionFeeAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin settings for SectionFee."""

    #  Need to add logic for exports
    list_display = ("section", "fee_type", "amount")
    list_filter = (
        "section__curriculum_course__curriculum__college",
        "section__curriculum_course__curriculum",
    )
    list_select_related = (
        "section__semester",
        "section",
        "section__curriculum_course",
    )
    search_fields = ("section", "section__curriculum_course")


@admin.register(Invoice)
class InvoiceAdmin(ScopedAutocompleteAdminMixin, SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin settings for Payment."""

    list_display = (
        "student_label",
        "curriculum_course",
        "semester_label",
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
        # "recorded_by",
    )
    readonly_fields = ("created_at",)
    inlines = (InvoicePaymentInline,)
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
        return queryset.annotate(payments_count=Count("payments"))

    @admin.display(description="Payments")
    def payments_link(self, obj: Invoice) -> str:
        """Return a clickable payment count for the invoice."""
        count = getattr(obj, "payments_count", 0)
        if not count:
            return "0"
        base_url = reverse("admin:finance_payment_changelist")
        query = urlencode({"invoice__id__exact": obj.id})
        return format_html('<a href="{}?{}">{}</a>', base_url, query, count)

    @admin.display(description="Student")
    def student_label(self, obj: Invoice) -> str:
        """Return the student name and ID for display."""
        student = obj.student
        name = student.long_name or student.user.get_full_name() or student.student_id
        student_id = student.student_id or "Pending ID"
        return f"{name} ({student_id})"

    @admin.display(description="Semester")
    def semester_label(self, obj: Invoice) -> str:
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


@admin.register(Payment)
class PaymentAdmin(ScopedAutocompleteAdminMixin, SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin interface for :class:`~app.finance.models.Payment`."""

    list_display = ("invoice", "amount_paid", "payment_method", "status", "recorded_by")
    autocomplete_fields = ("payment_method", "invoice", "status")
    exclude = ("recorded_by",)
    list_filter = (SemesterFilterAC,)
    list_select_related = (
        "invoice",
        "invoice__semester",
        "invoice__student",
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


@admin.register(ClearanceStatus, FeeType, PaymentMethod)
class LookupAdmin(admin.ModelAdmin):
    """Basic admin for finance lookup tables."""

    search_fields = ("code", "label")
    list_display = ("label",)
