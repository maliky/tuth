"""A module with function to ensure people exists in the DB."""

from typing import Dict

from app.people.ensure_people import ensure_person
from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.people.utils import NameParts, split_name
from app.shared.types import AbstractPersonT

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
    FACULTY_CACHE[cache_key] = fac_obj

    return fac_obj
