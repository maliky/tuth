"""
Re-export helper functions so management commands can do:

    from app.shared.populate_helpers import log, populate_colleges, ...
"""

from .auth import (
    ensure_role_groups,
    ensure_superuser,
    upsert_test_users_and_roles,
)

from .perms import (
    grant_college_object_perms,
    grant_model_level_perms,
)
from .utils import log, populate_colleges

__all__ = [
    "log",
    "populate_colleges",
    "ensure_superuser",
    "ensure_role_groups",
    "upsert_test_users_and_roles",
    "grant_model_level_perms",
    "grant_college_object_perms",
]
