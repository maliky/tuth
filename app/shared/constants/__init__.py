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
    DEFAULT_ROLE_TO_COLLEGE,
    MODEL_APP,
    OBJECT_PERM_MATRIX,
    TEST_PW,
    USER_ROLES,
)
from .registry import DOCUMENT_TYPES, StatusRegistration


STYLE_DEFAULT = "NOTICE"

__ALL__ = [
    "APPROVED",
    "CLEARANCE_CHOICES",
    "COLLEGE_CHOICES",
    "COURSE_PATTERN",
    "DEFAULT_ROLE_TO_COLLEGE",
    "DOCUMENT_TYPES",
    "FeeTypeLabels",
    "OBJECT_PERM_MATRIX",
    "PaymentMethod",
    "STATUS_CHOICES",
    "STATUS_CHOICES_PER_MODEL",
    "STYLE_DEFAULT",
    "StatusRegistration",
    "StatusReservation",
    "TEST_ENVIRONMENTAL_STUDIES_CURRICULUM",
    "TEST_PW",
    "TUITION_RATE_PER_CREDIT",
    "UNDEFINED_CHOICES",
    "USER_ROLES",
]
