"""Admin mixins for object filtering by user affiliation."""

from __future__ import annotations

from typing import Optional, cast

from django.contrib.admin import ModelAdmin
from django.http import HttpRequest
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.academics.models.college import College
from app.academics.models.department import Department
from app.people.models.staffs import Staff
from app.people.models.faculty import Faculty
from app.shared.admin.filters import resolve_scoped_filter_lookups


class ScopedAutocompleteAdminMixin(ModelAdmin):
    """Allow scoped autocomplete filters to pass admin lookup validation.

    Django's admin only allows query parameters that match static list_filter
    parameter names. ScopedAutocompleteFilter resolves related lookups at
    runtime, so we whitelist those resolved parameters here.

    Example:
        class SectionAdmin(ScopedAutocompleteAdminMixin, CollegeRestrictedAdmin):
            ...
    """

    def lookup_allowed(
        self, lookup: str, value: str | None, request: HttpRequest | None = None
    ) -> bool:
        """Return True when a lookup is allowed for the admin.

        Args:
            lookup: Query string parameter name.
            value: Query string parameter value.
            request: HTTP request, if available.

        Returns:
            True when the lookup is allowed.

        Example:
            >>> admin.lookup_allowed("section__semester", "1", request)
            True
        """
        if request is not None:
            # Allow dynamic list_filter parameters produced by ScopedAutocompleteFilter.
            dynamic_lookups = resolve_scoped_filter_lookups(
                self.model, self.get_list_filter(request)
            )
            if lookup in dynamic_lookups:
                return True
        # Normalize None for legacy lookup_allowed signatures in stubs.
        safe_value = value or ""
        return super().lookup_allowed(lookup, safe_value)


class CollegeRestrictedAdmin(
    ScopedAutocompleteAdminMixin,
    SimpleHistoryAdmin,
    ImportExportModelAdmin,
    GuardedModelAdmin,
):
    """Limit queryset to objects within the user's college."""

    college_field: str = "college"

    def get_user_college(self, request) -> Optional["College"]:
        """Return the college assigned to the current faculty."""
        try:
            return cast(College, request.user.staff.faculty.college)
        except (AttributeError, Faculty.DoesNotExist, Staff.DoesNotExist):
            return None

    def get_queryset(self, request):
        """Filter queryset to the user's college when one is linked."""
        qs = super().get_queryset(request)
        college = self.get_user_college(request)
        if request.user.is_superuser or college is None:
            return qs

        return qs.filter(**{self.college_field: college})


class DepartmentRestrictedAdmin(
    ScopedAutocompleteAdminMixin,
    SimpleHistoryAdmin,
    ImportExportModelAdmin,
    GuardedModelAdmin,
):
    """Limit queryset to objects within the user's department."""

    department_field: str = "department"

    def get_user_department(self, request) -> Optional["Department"]:
        """Return the department assigned to the current faculty."""
        try:
            return cast(Department, request.user.staff.department)
        except (AttributeError, Staff.DoesNotExist):
            return None

    def get_queryset(self, request):
        """Returns the query limited to the user's department if any."""
        qs = super().get_queryset(request)
        dept = self.get_user_department(request)

        if request.user.is_superuser or dept is None:
            return qs

        return qs.filter(**{self.department_field: dept})
