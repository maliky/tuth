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


__all__ = ["FacultyAdmin"]
