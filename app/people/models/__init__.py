"""Initialization for the models package."""

from app.people.models.donor import Donor
from app.people.models.student import Student
from app.people.models.staffs import Staff
from app.people.models.faculty import Faculty, FacultyManager
from app.people.models.object_manager import PersonManager
from .role_assignment import RoleAssignment

__all__ = [
    "Donor",
    "Faculty",
    "FacultyManager",
    "PersonManager",
    "RoleAssignment",
    "Staff",
    "Student",
]
