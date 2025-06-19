"""Authentication helpers and permission constants."""

from .helpers import (
    ensure_role_groups,
    ensure_superuser,
    upsert_test_users_and_roles,
)
from .perms import (
    DEFAULT_ROLE_TO_COLLEGE,
    MODEL_APP,
    OBJECT_PERM_MATRIX,
    TEST_PW,
    UserRole,
)
from .perms_helpers import grant_college_object_perms, grant_model_level_perms

__all__ = [
    "ensure_superuser",
    "ensure_role_groups",
    "upsert_test_users_and_roles",
    "DEFAULT_ROLE_TO_COLLEGE",
    "MODEL_APP",
    "OBJECT_PERM_MATRIX",
    "TEST_PW",
    "UserRole",
    "grant_model_level_perms",
    "grant_college_object_perms",
]
