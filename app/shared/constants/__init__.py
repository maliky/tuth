import re
from .choices import (
    APPROVED,
    UNDEFINED_CHOICES,
    CLEARANCE_CHOICES,
    COLLEGE_CHOICES,
    DOCUMENT_TYPES,
    STATUS_CHOICES_PER_MODEL,
    STATUS_CHOICES,
    StatusRegistration,
    StatusReservation,
    FeeTypeLabels,
)

from .curriculum import TEST_ENVIRONMENTAL_STUDIES_CURRICULUM

from .perms import (
    TEST_PW,
    OBJECT_PERM_MATRIX,
    MODEL_APP,
)

from .roles import (
    USER_ROLES,
    DEFAULT_ROLE_TO_COLLEGE,
)

MAX_STUDENT_CREDITS= 18
STYLE_DEFAULT = "NOTICE"
COURSE_PATTERN = re.compile(
    r"(?P<dept>[A-Z]{2,4})[_-]?(?P<num>[0-9]{3})(?:\s*-\s*(?P<college>[A-Z]{3,4}))?"
)

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
]
