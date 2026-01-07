"""A module with function to ensure people exists in the DB."""

from typing import Dict, Type, cast, Mapping
from app.people.models.faculty import Faculty
from app.people.models.staff import Staff
from app.shared.types import AbstractPersonT
from app.people.utils import NameParts

FACULTY_CACHE: Dict[str, Faculty] = {}


def ensure_person(
    model: Type[AbstractPersonT],
    *,
    username: str,
    name: NameParts,
    defaults: Mapping[str, str] | None = None,
) -> AbstractPersonT:
    """Ensure a person exists using the model manager (username-first, then fuzzy name)."""

    # Adding default values if not set.
    _defaults = dict(defaults or {})
    _defaults.update(name.to_dict())

    lookup = {"username": username}
    person, _ = model.objects.update_or_create(defaults=_defaults, **lookup)
    return cast(AbstractPersonT, person)


def ensure_faculty(username: str, name: NameParts) -> Faculty:
    """Look-up or create a faculty based on username or name parts."""

    cached = FACULTY_CACHE.get(username, None)
    if cached:
        return cached

    staff_profile = ensure_person(Staff, username=username, name=name)

    fac_obj, _ = Faculty.objects.get_or_create(staff_profile=staff_profile)
    FACULTY_CACHE[fac_obj.username] = fac_obj

    return fac_obj
