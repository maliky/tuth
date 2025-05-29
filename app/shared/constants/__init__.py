from app.shared.constants.academics import COLLEGE_CHOICES, MAX_STUDENT_CREDITS

from .academics import COLLEGE_CHOICES, COURSE_PATTERN, MAX_STUDENT_CREDITS
from .choices import (
    APPROVED,
    CLEARANCE_CHOICES,
    STATUS_CHOICES,
    STATUS_CHOICES_PER_MODEL,
    UNDEFINED_CHOICES,
)
from .curriculum import TEST_ENVIRONMENTAL_STUDIES_CURRICULUM
from .finance import (
    TUITION_RATE_PER_CREDIT,
    FeeTypeLabels,
    PaymentMethod,
    StatusReservation,
)
from .perms import (
    MODEL_APP,
    OBJECT_PERM_MATRIX,
    TEST_PW,
    DEFAULT_ROLE_TO_COLLEGE,
    USER_ROLES,
)
from .registry import DOCUMENT_TYPES, StatusRegistration

STYLE_DEFAULT = "NOTICE"

__ALL__ = [
    "APPROVED",
    "STYLE_DEFAULT",
    "COURSE_PATTERN",
    "UNDEFINED_CHOICES",
    "CLEARANCE_CHOICES",
    "COLLEGE_CHOICES",
    "DOCUMENT_TYPES",
    "STATUS_CHOICES_PER_MODEL",
    "StatusRegistration",
    "StatusReservation",
    "STATUS_CHOICES",
    "TEST_ENVIRONMENTAL_STUDIES_CURRICULUM",
    "TEST_PW",
    "OBJECT_PERM_MATRIX",
    "USER_ROLES",
    "DEFAULT_ROLE_TO_COLLEGE",
    "FeeTypeLabels",
    "StatusReservation",
    "PaymentMethod",
    "TUITION_RATE_PER_CREDIT",
]
