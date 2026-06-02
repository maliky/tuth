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

User = get_user_model()
ModelT: TypeAlias = models.Model

MERGE_USER_FIELDS = (
    "first_name",
    "last_name",
    "username",
    "email",
)


def _user_admin_link(user: UserModel | None) -> str:
    """Return a link to the auth user change page for admin lists."""
    if not user:
        return "-"
    url = reverse("admin:auth_user_change", args=[user.pk])
    label = user.username or str(user.pk)
    return format_html('<a href="{}">{}</a>', url, label)


class UserFullNameChoiceField(forms.ModelChoiceField):
    """ModelChoiceField that shows full user names for admin widgets."""

    def label_from_instance(self, obj: UserModel) -> str:
        full_name = obj.get_full_name() or obj.username
        staff_id = getattr(getattr(obj, "staff", None), "staff_id", "")
        student_id = getattr(getattr(obj, "student", None), "student_id", "")
        suffix = staff_id or student_id
        return f"{full_name} ({suffix})" if suffix else full_name


# ---- User admin with merge action ----

try:
    dj_admin.site.unregister(User)
    dj_admin.site.unregister(Group)
except Exception:
    pass


@dj_admin.register(User)
class MergeableUserAdmin(MergeWizardMixin, DuplicatePreviewMixin, dj_admin.ModelAdmin):
    """Lightweight user admin with merge action."""

    duplicate_threshold = 0.9
    merge_fields = MERGE_USER_FIELDS
    list_display = (
        "full_name",
        "username",
        "is_active",
        "duplicate_count_link",
        "possible_duplicates",
    )
    list_filter = ("groups",)
    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
        "staff__staff_id",
        "staff__long_name",
        "student__student_id",
        "student__long_name",
    )

    @admin.display(description="Full Name")
    def full_name(self, obj):
        """Return the full name for admin listings."""
        full_name = obj.get_full_name()
        return full_name or obj.username

    def get_autocomplete_result_label(self, result):
        """Show full-name labels in user autocomplete widgets."""
        field = UserFullNameChoiceField(queryset=User.objects.none())
        return field.label_from_instance(result)

    def merge_object_label(self, obj: ModelT) -> str:
        """Use full name labels in merge forms."""
        field = UserFullNameChoiceField(queryset=User.objects.none())
        return field.label_from_instance(cast(UserModel, obj))

    def _get_long_name(self, obj: UserModel) -> str:
        """Return the full name (or username) for duplicate checks."""
        full_name = obj.get_full_name()
        return full_name or obj.username

    def _duplicate_candidates(self, obj: UserModel) -> tuple[str, models.QuerySet]:
        """Return base name and candidate queryset for user duplicates."""
        base_name = self._get_long_name(obj)
        if not obj.last_name:
            return base_name, obj.__class__.objects.none()
        qs = obj.__class__.objects.exclude(pk=obj.pk).filter(
            last_name__iexact=obj.last_name
        )
        return base_name, qs

    def merge_records(self, target: ModelT, sources: Iterable[ModelT]) -> None:
        """Merge selected users into the chosen target user."""
        target_user = cast(UserModel, target)
        for source in sources:
            merge_users(target_user, cast(UserModel, source))

    def possible_duplicates(self, obj):
        """Reuse the duplicate preview logic at the user level."""
        # We are missing the middle name here.
        matches = self._duplicate_matches(obj)[:3]
        if not matches:
            return ""
        safe_rows = []
        for other, score in matches:
            other_user = cast(UserModel, other)
            url = reverse(
                f"admin:{other._meta.app_label}_{other._meta.model_name}_change",
                args=[other.pk],
            )
            safe_rows.append((url, other_user.username, f"{score:.2f}"))
        return format_html_join(
            ", ",
            '<a href="{}">{}</a> ({})',
            safe_rows,
        )

    possible_duplicates.admin_order_field = "duplicate_score_sort"  # type: ignore[attr-defined]


@admin.register(Faculty)
class FacultyAdmin(
    MergeWizardMixin, DuplicatePreviewMixin, CollegeRestrictedNoHistoryAdmin
):
    """Admin options for :class:~app.people.models.Faculty.

    Displays the staff profile with optional filtering by college. The faculty
    resource is used for import/export operations.
    """

    # form =
    resource_class = FacultyResource
    form = FacultyForm
    merge_fields = (
        "staff_profile__user__first_name",
        "staff_profile__user__last_name",
        "staff_profile__user__username",
        "staff_profile__user__email",
        "staff_profile__middle_name",
        "staff_profile__prefix_name",
        "staff_profile__suffix_name",
        "staff_profile__phone_number",
        "staff_profile__physical_address",
        "staff_profile__birth_date",
        "staff_profile__bio",
        "staff_profile__photo",
        "staff_profile__nationality",
        "staff_profile__origin_county",
        "staff_profile__marital_status",
        "staff_profile__gender",
        "staff_profile__division",
        "staff_profile__department",
        "staff_profile__employment_date",
        "staff_profile__position",
        "college",
        "google_profile",
        "personal_website",
        "academic_rank",
    )

    list_display = (
        "faculty_name",
        "faculty_staff_id",
        "username",
        "academic_rank",
        "primary_assignment",
        "get_division",
        "get_dpt",
        "possible_duplicates",
    )
    list_filter = [
        DptFltAC,
        FacultyTeachingDptFltAC,
        FacultyGpFAC,
        "college",
    ]

    search_fields = (
        "staff_profile__staff_id",
        "staff_profile__long_name",
        "staff_profile__user__first_name",
        "staff_profile__user__last_name",
        "academic_rank",
    )
    autocomplete_fields = ("staff_profile", "college")
    inlines = [SecIL]
    readonly_fields = ("staff_bio",)
    fieldsets = [
        (
            "User Information",
            {
                "fields": FacultyForm.USER_FIELDS,
                "description": (
                    "Username / e-mail are auto-generated from the name fields. "
                    "To change the password you need to open the user box."
                ),
            },
        ),
        ("Faculty Information", {"fields": FacultyForm.FACULTY_FIELDS}),
        # > maybe better to just add staff_bio to FACULTY_FIELDS
        ("Staff Bio", {"fields": ("staff_bio",)}),
        (
            "Work Information",
            {
                "classes": ["collapse"],
                "fields": FacultyForm.STAFF_FIELDS,
            },
        ),
    ]

    def get_queryset(self, request):
        """Select related staff/profile data to speed up change views."""
        qs = super().get_queryset(request)
        return qs.select_related(
            "staff_profile__user",
            "staff_profile__department",
            "college",
        )

    @admin.display(description="Long Name", ordering="staff_profile__user__first_name")
    def faculty_name(self, obj):
        """Add the long name to the admin."""
        return obj.staff_profile.long_name

    @admin.display(description="Faculty Staff ID", ordering="staff_profile__staff_id")
    def faculty_staff_id(self, obj):
        """Add the long name to the admin."""
        return obj.staff_profile.staff_id

    @admin.display(description="Username", ordering="staff_profile__user__username")
    def username(self, obj):
        """Link the staff user for password edits."""
        staff_profile = getattr(obj, "staff_profile", None)
        return _user_admin_link(getattr(staff_profile, "user", None))

    @admin.display(description="Primary Assignment")
    def primary_assignment(self, obj):
        """Show the department/college that receives most sections for the faculty."""
        return obj.primary_assignment_label or "-"

    @admin.display(description="Bio")
    def staff_bio(self, obj):
        """Show the staff bio."""
        return obj.staff_profile.bio or "-"

    def merge_object_label(self, obj: ModelT) -> str:
        """Label faculty choices with staff names."""
        faculty = cast(Faculty, obj)
        return faculty.staff_profile.long_name or str(faculty)

    def merge_records(self, target: ModelT, sources: Iterable[ModelT]) -> None:
        """Merge faculty through their staff profiles."""
        faculty_target = cast(Faculty, target)
        for source in sources:
            merge_people(
                faculty_target.staff_profile, cast(Faculty, source).staff_profile
            )

    def sync_merge_target(self, target: ModelT) -> None:
        """Sync staff profile fields after merging."""
        faculty_target = cast(Faculty, target)
        staff = faculty_target.staff_profile
        staff._update_long_name()
        staff.username = staff.user.username
        staff.email = staff.user.email
        staff.save()


@admin.register(Donor)
class DonorAdmin(MergeWizardMixin, SimpleHistoryAdmin, GuardedModelAdmin):
    """Admin management for :class:~app.people.models.Donor.

    Shows each donor's user and ID with autocomplete for the user relation.
    """

    form = DonorForm
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
    )
    list_display = ("long_name", "donor_id", "username", "donor_bio")
    search_fields = ("donor_id", "long_name", "user__first_name", "user__last_name")
    readonly_fields = ("donor_id",)
    fieldsets = [
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
        (None, {"fields": PersonFormMixin.STANDARD_USER_FIELDS}),
    ]

    @admin.display(description="Bio")
    def donor_bio(self, obj):
        """Show a short excerpt of the donor bio column."""
        if not obj.bio:
            return ""
        return obj.bio if len(obj.bio) <= 80 else f"{obj.bio[:77]}…"

    @admin.display(description="Username", ordering="user__username")
    def username(self, obj):
        """Link the donor user for password edits."""
        return _user_admin_link(getattr(obj, "user", None))

    def merge_object_label(self, obj: ModelT) -> str:
        """Use donor long name labels in merge forms."""
        donor = cast(Donor, obj)
        return donor.long_name or str(donor)

    def merge_records(self, target: ModelT, sources: Iterable[ModelT]) -> None:
        """Merge selected donors into the chosen target."""
        target_donor = cast(Donor, target)
        for source in sources:
            merge_people(target_donor, cast(Donor, source))


@admin.register(Staff)
class StaffAdmin(MergeWizardMixin, DuplicatePreviewMixin, DptRestrictedAdmin):
    """Admin management for :class:~app.people.models.Staff.

    Provides detailed fieldsets for personal and work information. Important
    fields like staff_id are read-only to avoid accidental edits.
    """

    form = StaffForm
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
        "division",
        "department",
        "position",
        "employment_date",
    )
    list_display = (
        "long_name",
        "staff_id",
        "username",
        "position",
        "roles",
        "possible_duplicates",
    )
    search_fields = (
        "staff_id",
        "long_name",
        "user__username",
        "user__first_name",
        "user__last_name",
        "department__code",
    )
    list_filter = ("user__groups",)
    ordering = ("staff_id",)
    readonly_fields = ("staff_id",)
    inlines = [DocStaffIL]
    fieldsets = [
        (
            "User Account",
            {
                "fields": PersonFormMixin.USER_FIELDS,
                "description": (
                    "Username / e-mail are auto-generated from the name fields. "
                    "To change the password you need to open the user box."
                ),
            },
        ),
        ("Personal Details", {"fields": PersonFormMixin.STANDARD_USER_FIELDS}),
        (
            "Work Information",
            {
                "classes": ["collapse"],
                "fields": StaffForm.SPECIFIC_FIELDS,
            },
        ),
    ]

    def merge_object_label(self, obj: ModelT) -> str:
        """Use staff long names in merge forms."""
        staff = cast(Staff, obj)
        return staff.long_name or str(staff)

    @admin.display(description="Username", ordering="user__username")
    def username(self, obj):
        """Link the staff user for password edits."""
        return _user_admin_link(getattr(obj, "user", None))

    def merge_records(self, target: ModelT, sources: Iterable[ModelT]) -> None:
        """Merge selected staff profiles into the chosen target."""
        target_staff = cast(Staff, target)
        for source in sources:
            merge_people(target_staff, cast(Staff, source))


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


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    list_display = ("user", "group", "start_date")
    autocomplete_fields = ("user", "group", "college", "department")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Use full-name labels for user selection."""
        if db_field.name == "user":
            kwargs["form_class"] = UserFullNameChoiceField
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@dj_admin.register(Group)
class GpAdmin(dj_admin.ModelAdmin):
    """Group admin with user counts."""

    list_display = ("name", "user_count_link")
    # Show group members on the change form for quick verification.
    readonly_fields = ("user_list",)
    fields = ("name", "permissions", "user_list")
    # > Required for RoleAssignmentAdmin autocomplete_fields on "group".
    search_fields = ("name",)

    def get_queryset(self, request):
        """Annotate user totals for groups."""
        qs = super().get_queryset(request)
        return qs.annotate(user_total=Count("user", distinct=True))

    @admin.display(description="Users", ordering="user_total")
    def user_count_link(self, obj):
        """Link to users filtered by the group."""
        count = getattr(obj, "user_total", None)
        if count is None:
            count = obj.user_set.count()
        url = reverse("admin:auth_user_changelist") + (f"?groups__id__exact={obj.id}")
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description="Members")
    def user_list(self, obj: Group) -> str:
        """Return a comma-separated list of member usernames."""
        return ", ".join(user.username for user in obj.user_set.all())
