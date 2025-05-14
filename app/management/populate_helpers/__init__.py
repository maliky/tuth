"""
Re-export helper functions so management commands can do:

    from app.populate_helpers import log, populate_colleges, ...
"""

# ---------- core utils ----------
from .utils import log, populate_colleges

# ---------- auth helpers ----------
from .auth import (
    ensure_superuser,
    ensure_role_groups,
    upsert_test_users_and_roles,
)

# ---------- permission helpers ----------
from .perms import (
    grant_model_level_perms,
    grant_college_object_perms,
)

# ---------- curriculum helpers ----------
from .curriculum import (
    populate_academic_years,
    populate_environmental_studies_curriculum,
)

__all__ = [
    # utils
    "log",
    "populate_colleges",
    # auth
    "ensure_superuser",
    "ensure_role_groups",
    "upsert_test_users_and_roles",
    # perms
    "grant_model_level_perms",
    "grant_college_object_perms",
    # curriculum
    "populate_academic_years",
    "populate_environmental_studies_curriculum",
]
