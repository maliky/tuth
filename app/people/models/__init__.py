"""Initialization for the models package."""

from .profile import StudentProfile, FacultyProfile, DonorProfile, StaffProfile
from .role_assignment import RoleAssignment

__all__ = [
    "StudentProfile",
    "FacultyProfile",
    "DonorProfile",
    "StaffProfile",
    "RoleAssignment",
]
