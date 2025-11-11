"""Initialization for the models package."""
# app/registry/models/__init__.py
from .document import (
    DocumentStaff,
    DocumentDonor,
    DocumentStudent,
    DocumentStatus,
    DocumentType,
)
from .grade import Grade, GradeValue
from .registration import Registration, RegistrationStatus
from .transcript import TranscriptRequest, TranscriptRequestStatus

__all__ = [
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
