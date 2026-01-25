"""Initialization for the models package."""

from .document import (
    DocumentStaff,
    DocumentDonor,
    DocumentStudent,
)
from .status_types import (
    DocumentStatus,
    DocumentType,
    RegistrationStatus,
    TranscriptRequestStatus,
)
from .grade import Grade, GradeValue
from .registration import Registration
from .transcript import TranscriptRequest
from .credit_hours import CreditHour

__all__ = [
    "CreditHour",
    "DocumentStaff",
    "DocumentType",
    "DocumentStatus",
    "DocumentDonor",
    "DocumentStudent",
    "Registration",
    "RegistrationStatus",
    "Grade",
    "GradeValue",
    "TranscriptRequest",
    "TranscriptRequestStatus",
]
