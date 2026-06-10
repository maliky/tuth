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


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(SimpleHistoryAdmin, GuardedModelAdmin):
    list_display = ("user", "group", "start_date")
    autocomplete_fields = ("user", "group", "college", "department")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Use full-name labels for user selection."""
        if db_field.name == "user":
            kwargs["form_class"] = UserFullNameChoiceField
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


__all__ = ["RoleAssignmentAdmin"]
