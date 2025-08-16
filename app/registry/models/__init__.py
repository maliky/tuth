"""Initialization for the models package."""

# app/registry/models/__init__.py
from .document import DocumentStaff, DocumentDonor, DocumentStudent
from .grade import Grade, GradeValue
from .registration import Registration

__all__ = [
    "DocumentStaff",
    "DocumentDonor",
    "DocumentStudent",
    "Registration",
    "Grade",
    "GradeValue",
]
