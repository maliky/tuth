"""A module with function to ensure people exists in the DB."""

from typing import Any, Dict, Type, cast, Mapping
from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.shared.types import AbstractPersonT
from app.people.utils import NameParts

FACULTY_CACHE: Dict[str, Faculty] = {}


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


def ensure_faculty(username: str, name: NameParts) -> Faculty:
    """Look-up or create a faculty based on username or name parts."""

    cached = FACULTY_CACHE.get(username, None)
    if cached:
        return cached

    staff_profile = ensure_person(Staff, username=username, name=name)

    fac_obj, _ = Faculty.objects.get_or_create(staff_profile=staff_profile)

    FACULTY_CACHE[fac_obj.staff_profile.username] = fac_obj

    return cast(Faculty, fac_obj)
