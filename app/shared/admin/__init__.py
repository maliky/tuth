"""Initialisation of the init module of the shared admin module."""

from app.shared.admin.core import get_current_semester
from app.shared.admin.mixins import CollegeRestrictedAdmin, DepartmentRestrictedAdmin

__all__ = [
    "get_current_semester",
    "CollegeRestrictedAdmin",
    "DepartmentRestrictedAdmin",
]
