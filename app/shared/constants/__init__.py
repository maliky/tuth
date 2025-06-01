from itertools import chain
from typing import List, Tuple

from .academics import (
    COLLEGE_CHOICES,
    COURSE_PATTERN,
    MAX_STUDENT_CREDITS,
    StatusCurriculum,
)
from .curriculum import TEST_ENVIRONMENTAL_STUDIES_CURRICULUM
from .finance import (
    TUITION_RATE_PER_CREDIT,
    FeeType,
    PaymentMethod,
    StatusClearance,
    StatusReservation,
)
from .perms import (
    DEFAULT_ROLE_TO_COLLEGE,
    MODEL_APP,
    OBJECT_PERM_MATRIX,
    TEST_PW,
    UserRole,
)
from .registry import DocumentType, StatusDocument, StatusRegistration

STYLE_DEFAULT = "NOTICE"

APPROVED: str = "approved"
UNDEFINED_CHOICES: str = "undefined_choice"
_raw = []
for s in [
    StatusClearance,
    StatusCurriculum,
    StatusDocument,
    StatusRegistration,
    StatusReservation,
]:
    _raw += s.choices
STATUS_CHOICES = list(set(_raw))


__ALL__ = [
    "APPROVED",
    "CLEARANCE_CHOICES",
    "COLLEGE_CHOICES",
    "COURSE_PATTERN",
    "DEFAULT_ROLE_TO_COLLEGE",
    "DocumentType",
    "FeeType",
    "OBJECT_PERM_MATRIX",
    "PaymentMethod",
    "STATUS_CHOICES",
    "STYLE_DEFAULT",
    "StatusRegistration",
    "StatusReservation",
    "StatusCurriculum",
    "StatusClearance",
    "StatusDocument",
    "TEST_ENVIRONMENTAL_STUDIES_CURRICULUM",
    "TEST_PW",
    "TUITION_RATE_PER_CREDIT",
    "UNDEFINED_CHOICES",
    "UserRole",
]
