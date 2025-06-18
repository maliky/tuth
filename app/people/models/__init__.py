"""Initialization for the models package."""

from app.people.models.donor import Donor
from app.people.models.student import Student
from app.people.models.staffs import Faculty, Staff

from .role_assignment import RoleAssignment

__all__ = [
    "Student",
    "Faculty",
    "Donor",
    "Staff",
    "RoleAssignment",
]
