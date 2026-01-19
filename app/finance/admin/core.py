"""Core module."""

from typing import Optional, cast

from app.finance.models.payment import FeeType, PaymentMethod, ClearanceStatus
from django import forms
from django.contrib import admin, messages
from guardian.admin import GuardedModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.academics.models.course import CurriculumCourse
from app.finance.models.payment import Payment
from app.finance.models.invoice import Invoice
from app.finance.models.scholarship import Scholarship
from app.people.models.staffs import Staff
from app.shared.admin.mixins import ScopedAutocompleteAdminMixin
from app.timetable.admin.filters import SemesterFilterAC
from app.timetable.models.semester import Semester


class StaffChoiceField(forms.ModelChoiceField):
    """ModelChoiceField that displays staff long names."""

    def label_from_instance(self, obj: Staff) -> str:
        return obj.long_name or str(obj)


@admin.register(Invoice)
class InvoiceAdmin(ScopedAutocompleteAdminMixin, SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin settings for Payment."""

    list_display = ("__str__", "recorded_by_name")
    list_filter = (SemesterFilterAC,)
    readonly_fields = ("created_at",)
    search_fields = (
        "curriculum_course__course__short_code",
        "student__student_id",
        "student__long_name",
        "student__user__username",
        "semester__academic_year__code",
    )
    autocomplete_fields = ("student", "recorded_by")

    @admin.display(description="Recorded by")
    def recorded_by_name(self, obj: Invoice) -> str:
        """Return the staff long name for display."""
        recorded_by = obj.recorded_by
        if recorded_by is not None:
            return recorded_by.long_name or str(recorded_by)
        return "-"

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
    list_display = ("label",)
