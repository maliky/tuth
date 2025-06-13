"""Initialization for the models package."""

from .profiles import Student, Faculty, Donor, Staff
from .role_assignment import RoleAssignment

__all__ = [
    "Student",
    "Faculty",
    "Donor",
    "Staff",
    "RoleAssignment",
]
