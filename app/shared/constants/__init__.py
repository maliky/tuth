from .choices import (
    APPROVED,
    UNDEFINED_CHOICES,
    CLEARANCE_CHOICES,
    COLLEGE_CHOICES,
    STATUS_CHOICES_PER_MODEL,
    STATUS_CHOICES,
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


STYLE_DEFAULT = "NOTICE"

__ALL__ = [
    "APPROVED",
    "STYLE_DEFAULT",
    "UNDEFINED_CHOICES",
    "CLEARANCE_CHOICES",
    "COLLEGE_CHOICES",
    "STATUS_CHOICES_PER_MODEL",
    "STATUS_CHOICES",
    "TEST_ENVIRONMENTAL_STUDIES_CURRICULUM",
    "TEST_PW",
    "OBJECT_PERM_MATRIX",
    "USER_ROLES",
    "DEFAULT_ROLE_TO_COLLEGE",
]
