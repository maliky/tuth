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


__all__ = ["DonorAdmin"]
