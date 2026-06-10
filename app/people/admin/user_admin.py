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


__all__ = ["GpAdmin", "MergeableUserAdmin", "UserFullNameChoiceField", "_user_admin_link"]
