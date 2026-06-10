"""Core module."""

from typing import Iterable, TypeAlias, cast

from django import forms
from django.contrib import admin
from django.contrib import admin as dj_admin
from django.contrib import messages
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, User as UserModel
from django.db import models
from django.db.models import Case, Count, F, FloatField, Q, Sum, When
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Round
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.academics.admin.filters import CurriFltAC, DptFltAC
from app.people.admin.filters import (
    FacultyGpFAC,
    FacultyTeachingDptFltAC,
    StdEnrolledCurriFltAC,
    StdCurriCrsFltAC,
    StdEntrySemFAC,
)
from app.people.admin.mixins import (
    DuplicatePreviewMixin,
    MergeWizardMixin,
)
from app.people.admin.resources import FacultyResource
from app.people.forms.base import PersonFormMixin
from app.people.forms.faculty import FacultyForm
from app.people.forms.person import (
    DonorForm,
    StaffForm,
    StdForm,
)
from app.people.models.donor import Donor
from app.people.models.faculty import Faculty
from app.people.models.role_assignment import RoleAssignment
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.people.services.merge_people import merge_people, merge_users
from app.registry.admin import (
    DocStaffIL,
    DocStdIL,
    StdGradeIL,
)
from app.registry.admin.core import _available_secs_for_std

# GPA should ignore non-final grade codes (kept in registry.constants).
from app.registry.constants import GPA_EXCLUDED_CODES
from app.registry.models.registration import Registration, RegistrationStatus
from app.shared.admin.filters import StdLevelFlt
from app.shared.admin.mixins import (
    CollegeRestrictedAdmin,
    CollegeRestrictedNoHistoryAdmin,
    DptRestrictedAdmin,
    ScopedAutocompleteAdminMixin,
)
from app.timetable.admin.filters import SemFltAC
from app.timetable.admin.inlines import SecIL
from app.timetable.models.section import Section

from app.people.admin.user_admin import UserFullNameChoiceField, _user_admin_link

User = get_user_model()
ModelT: TypeAlias = models.Model

MERGE_USER_FIELDS = (
    "first_name",
    "last_name",
    "username",
    "email",
)


class StdRegioForm(StdForm):
    """Student form that supports bulk registration selection."""

    registration_sections = forms.ModelMultipleChoiceField(
        queryset=Section.objects.none(),
        required=False,
        widget=FilteredSelectMultiple("Sections", False),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        student = self.instance if getattr(self.instance, "pk", None) else None
        sections_qs = _available_secs_for_std(student)
        sections_field = self.fields.get("registration_sections")
        if sections_field is not None and isinstance(
            sections_field, forms.ModelMultipleChoiceField
        ):
            sections_field.queryset = sections_qs
            if not student:
                sections_field.help_text = "Save the student to load available sections."
                sections_field.disabled = True
            elif not sections_qs.exists():
                sections_field.help_text = (
                    "No available sections for the current open semester."
                )


@admin.register(Student)
class StdAdmin(
    ScopedAutocompleteAdminMixin,
    MergeWizardMixin,
    DuplicatePreviewMixin,
    SimpleHistoryAdmin,
    ImportExportModelAdmin,
    GuardedModelAdmin,
):
    """Admin interface for :class:~app.people.models.Student.

    list_display shows the related user and student ID with search enabled
    on both fields. Import/export is supported via ImportExportModelAdmin.
    """

    form = StdRegioForm
    merge_fields = (
        "user__first_name",
        "user__last_name",
        "user__username",
        "user__email",
        "middle_name",
        "prefix_name",
        "suffix_name",
        "phone_number",
        "physical_address",
        "birth_date",
        "bio",
        "photo",
        "nationality",
        "origin_county",
        "marital_status",
        "gender",
        "curricula",
        "last_enrolled_semester",
        "entry_semester",
        "last_school_attended",
        "reason_for_leaving",
        "father_name",
        "father_address",
        "mother_name",
        "mother_address",
        "emergency_contact",
    )
    STUDENT_FIELDS = (
        "student_id",
        "primary_curriculum",
        "last_enrolled_semester",
        "entry_semester",
        "max_credit_hours",
    )
    BIO_FIELDS = (
        "last_school_attended",
        "reason_for_leaving",
        "father_name",
        "father_address",
        "mother_name",
        "mother_address",
        "emergency_contact",
        "nationality",
        "origin_county",
        "marital_status",
        "gender",
    )
    list_display = (
        "long_name",
        "student_id",
        "username",
        "cumulative_gpa",
        "validated_credits",
        "primary_curriculum_display",
        # "entry_semester",
        # "last_enrolled_semester",
        "entry_semester",
        "last_enrolled_semester",
        "birth_date",
        "duplicate_count_link",
        "possible_duplicates",
    )
    search_fields = (
        "student_id",
        "long_name",
        "user__username",
        "user__first_name",
        "user__last_name",
    )
    # list_editable = ("curriculum",)
    list_filter = (
        SemFltAC,
        CurriFltAC,
        StdEnrolledCurriFltAC,
        StdEntrySemFAC,
        StdLevelFlt,
        StdCurriCrsFltAC,
        "curricula__college",
    )
    readonly_fields = ("student_id",)
    inlines = [StdGradeIL, DocStdIL]
    list_select_related = ("entry_semester", "last_enrolled_semester")
    fieldsets = [
        (
            "Student Informations",
            {
                "fields": STUDENT_FIELDS,
            },
        ),
        ("Student Bio", {"classes": ["collapse"], "fields": BIO_FIELDS}),
        (
            "User Account",
            {
                "classes": ["collapse"],
                "fields": PersonFormMixin.USER_FIELDS,
                "description": (
                    "Username / e-mail are auto-generated from the name fields. "
                    "To change the password you need to open the user box."
                ),
            },
        ),
        (
            "User Details",
            {"classes": ["collapse"], "fields": PersonFormMixin.STANDARD_USER_FIELDS},
        ),
        (
            "Adding new Registrations",
            {
                "fields": ("registration_sections",),
                "description": (
                    "Select sections to register the student for the current open "
                    "semester."
                ),
            },
        ),
    ]

    # -------------- helpers for readonly panel --------------
    def get_queryset(self, request):
        """Annotate GPA aggregates for the list display."""
        qs = (
            super()
            .get_queryset(request)
            .prefetch_related("curriculum_enrollments__curriculum")
        )
        grade_filter = Q(grade__value__number__isnull=False) & ~Q(
            grade__value__code__in=GPA_EXCLUDED_CODES
        )
        grade_points = ExpressionWrapper(
            F("grade__value__number")
            * F("grade__section__curriculum_course__credit_hours_id"),
            output_field=FloatField(),
        )
        qs = qs.annotate(
            gpa_quality_points=Sum(grade_points, filter=grade_filter),
            gpa_credit_total=Sum(
                "grade__section__curriculum_course__credit_hours_id",
                filter=grade_filter,
            ),
            validated_credits_total=Sum(
                "grade__section__curriculum_course__credit_hours_id",
                filter=Q(grade__value__number__gte=1),
            ),
        )
        # There is a problem here I get whole gpa only
        return qs.annotate(
            gpa_value=Case(
                When(
                    gpa_credit_total__gt=0,
                    then=Round(
                        ExpressionWrapper(
                            F("gpa_quality_points") / F("gpa_credit_total"),
                            output_field=FloatField(),
                        ),
                        precision=2,
                    ),
                ),
                default=None,
                output_field=FloatField(),
            ),
            gpa_sort_value=Case(
                When(gpa_credit_total__gt=0, then=F("gpa_value")),
                default=-1.0,
                output_field=FloatField(),
            ),
            validated_credits_sort_value=Case(
                When(
                    validated_credits_total__isnull=False,
                    then=F("validated_credits_total"),
                ),
                default=0.0,
                output_field=FloatField(),
            ),
        )

    @admin.display(description="Cumulative GPA", ordering="gpa_sort_value")
    def cumulative_gpa(self, obj):
        """Return the cumulative GPA computed from graded sections."""
        gpa_value = getattr(obj, "gpa_value", None)
        if gpa_value is None:
            return "-"
        return f"{gpa_value:.2f}"

    @admin.display(
        description="Validated Credits", ordering="validated_credits_sort_value"
    )
    def validated_credits(self, obj):
        """Return the cumulative credits validated by the student."""
        total = getattr(obj, "validated_credits_total", 0) or 0
        return int(total)

    @admin.display(description="Username", ordering="user__username")
    def username(self, obj):
        """Link the student user for password edits."""
        return _user_admin_link(getattr(obj, "user", None))

    @admin.display(description="Curriculum")
    def primary_curriculum_display(self, obj):
        """Render the canonical primary curriculum label."""
        return str(obj.primary_curriculum)

    def save_model(self, request, obj, form, change):
        """Save the model and create selected registrations."""
        # The form.save() handles creating and linking the User.
        obj.save()
        sections = list(
            cast(
                list[Section],
                form.cleaned_data.get("registration_sections") or [],
            )
        )
        if not sections:
            return
        status = RegistrationStatus.get_dft()
        created_count = 0
        skipped_count = 0
        for section in sections:
            _, created = Registration.objects.get_or_create(
                student=obj,
                section=section,
                defaults={"status": status},
            )
            if created:
                created_count += 1
            else:
                skipped_count += 1
        if created_count or skipped_count:
            level = messages.SUCCESS if created_count else messages.WARNING
            self.message_user(
                request,
                (
                    f"Created {created_count} registration(s). "
                    f"Skipped {skipped_count} existing registration(s)."
                ),
                level=level,
            )

    def merge_object_label(self, obj: ModelT) -> str:
        """Use student long names in merge forms."""
        student = cast(Student, obj)
        return student.long_name or str(student)

    def merge_records(self, target: ModelT, sources: Iterable[ModelT]) -> None:
        """Merge selected students into the chosen target."""
        target_student = cast(Student, target)
        for source in sources:
            merge_people(target_student, cast(Student, source))


__all__ = ["StdAdmin", "StdRegioForm"]
