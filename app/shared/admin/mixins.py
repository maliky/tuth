"""Admin mixins for object filtering by user affiliation."""

from __future__ import annotations

from typing import Optional, cast


from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.academics.models.college import College
from app.academics.models.department import Department
from app.people.models.staffs import Staff
from app.people.models.faculty import Faculty


class CollegeRestrictedAdmin(
    SimpleHistoryAdmin, ImportExportModelAdmin, GuardedModelAdmin
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
        """Returns a filtered query set if a college is linked to the user making the request."""
        qs = super().get_queryset(request)
        college = self.get_user_college(request)
        if request.user.is_superuser or college is None:
            return qs

        return qs.filter(**{self.college_field: college})


class DepartmentRestrictedAdmin(
    SimpleHistoryAdmin, ImportExportModelAdmin, GuardedModelAdmin
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
