"""Compatibility façade for people admin registrations."""

from __future__ import annotations

from app.people.admin.donor_admin import DonorAdmin
from app.people.admin.faculty_admin import FacultyAdmin
from app.people.admin.role_admin import RoleAssignmentAdmin
from app.people.admin.staff_admin import StaffAdmin
from app.people.admin.student_admin import StdAdmin, StdRegioForm
from app.people.admin.user_admin import (
    GpAdmin,
    MergeableUserAdmin,
    UserFullNameChoiceField,
    _user_admin_link,
)

__all__ = [
    "DonorAdmin",
    "FacultyAdmin",
    "GpAdmin",
    "MergeableUserAdmin",
    "RoleAssignmentAdmin",
    "StaffAdmin",
    "StdAdmin",
    "StdRegioForm",
    "UserFullNameChoiceField",
    "_user_admin_link",
]
