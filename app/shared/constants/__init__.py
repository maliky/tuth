"""Expose shared constants and enumerations used throughout the project."""

from itertools import chain
from typing import List, Tuple

from .academics import COURSE_PATTERN, MAX_STUDENT_CREDITS
from .curriculum import TEST_ENVIRONMENTAL_STUDIES_CURRICULUM
from .finance import TUITION_RATE_PER_CREDIT
from .registry import DocumentType, StatusDocument, StatusRegistration


STYLE_DEFAULT = "NOTICE"

APPROVED: str = "approved"
UNDEFINED_CHOICES: str = "undefined_choice"
_raw = []
for s in [
    StatusDocument,
    StatusRegistration,
]:
    _raw += s.choices

# Does not preserve the order but does not matter.
STATUS_CHOICES = list(set(_raw))


__all__ = [
    "APPROVED",
    "COURSE_PATTERN",
    "DocumentType",
    "STATUS_CHOICES",
    "STYLE_DEFAULT",
    "StatusDocument",
    "StatusRegistration",
    "TEST_ENVIRONMENTAL_STUDIES_CURRICULUM",
    "TUITION_RATE_PER_CREDIT",
    "UNDEFINED_CHOICES",
]
