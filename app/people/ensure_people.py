"""A module with function to ensure people exists in the DB."""

from typing import Dict, Tuple

from app.people.models.faculty import Faculty

FACULTY_CACHE: Dict[Tuple[str, int], Faculty] = {}


def ensure_faculty(username, **kwargs) -> Faculty:
    """Look-up or create a faculty is returned."""
    cached = FACULTY_CACHE.get(username, None)
    if cached:
        return cached

    fac_obj, _ = Faculty.objects.get_or_create(username=username, **kwargs)
    FACULTY_CACHE[fac_obj.username] = fac_obj

    return fac_obj
