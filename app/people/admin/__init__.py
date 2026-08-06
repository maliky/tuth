"""Initialization for the admin package."""

from .filters import FacultyGpFAC, StdEntrySemFAC
from .resources import DonorResource, FacultyResource, StdResource
from .core import StdAdmin, DonorAdmin, FacultyAdmin
from .enrollment_application_admin import (
    EnrollmentApplicationAdmin,
    EnrollmentApplicationDocAdmin,
    EnrollmentCommunicationAdmin,
    EnrollmentEmailTemplateAdmin,
)


__all__ = [
    "DonorAdmin",
    "DonorResource",
    "EnrollmentApplicationAdmin",
    "EnrollmentApplicationDocAdmin",
    "EnrollmentCommunicationAdmin",
    "EnrollmentEmailTemplateAdmin",
    "FacultyAdmin",
    "FacultyGpFAC",
    "FacultyResource",
    "RoleAssignmentAdmin",
    "StdAdmin",
    "StdEntrySemFAC",
    "StdResource",
]
