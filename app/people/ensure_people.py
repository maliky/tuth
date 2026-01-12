"""A module with function to ensure people exists in the DB."""

from typing import Any, Dict, Mapping, Type, cast

from app.people import ensures as student_ensures
from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.shared.types import AbstractPersonT
from app.people.utils import NameParts

FACULTY_CACHE: Dict[str, Faculty] = {}
STUDENT_ID_CACHE = student_ensures.STUDENT_ID_CACHE


def ensure_person(
    model: Type[AbstractPersonT],
    *,
    username: str | None,
    name: NameParts,
    defaults: Mapping[str, Any] | None = None,
) -> AbstractPersonT:
    """Ensure a person (model) exists using its own manager.

    (username-first, then fuzzy name search),
    Name has precedences but can be completed with defaults.
    """

    # Adding default values if not set.
    merged: Dict[str, Any] = dict(defaults or {})
    merged.update(name.to_dict())
    lookup: Mapping[str, Any] = {"username": username} if username else {}
    # this objects manager is a bit diferent and will do a search on name fiels
    # found in defaults also
    person, _ = model.objects.get_or_create(defaults=merged, **lookup)
    return cast(AbstractPersonT, person)


def _faculty_cache_key(username: str | None, name: NameParts) -> str:
    """Return a stable cache key for a faculty lookup."""
    if username:
        return f"username:{username}"
    name_key = name.to_string(full=True)
    return f"name:{name_key}" if name_key else "name:"


def ensure_faculty(username: str | None, name: NameParts) -> Faculty:
    """Look up or create a faculty based on username or name parts."""

    cache_key = _faculty_cache_key(username, name)
    cached = FACULTY_CACHE.get(cache_key, None)
    if cached:
        return cached

    staff_profile = ensure_person(Staff, username=username, name=name)

    fac_obj, _ = Faculty.objects.get_or_create(staff_profile=staff_profile)

    FACULTY_CACHE[cache_key] = fac_obj
    if staff_profile.username:
        FACULTY_CACHE[f"username:{staff_profile.username}"] = fac_obj

    return cast(Faculty, fac_obj)
