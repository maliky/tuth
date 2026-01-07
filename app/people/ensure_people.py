"""A module with function to ensure people exists in the DB."""

from app.people.models.faculty import Faculty

FACULTY_CACHE: Dict[Tuple[str, int], Semester] = {}


def ensure_faculty(username, **kwargs) -> Faculty:
    """Look-up or create a faculty is returned."""
    cached = FACULTY_CACHE[username]
    if cached:
        return cached

    fac_obj, _ = Faculty.objects.get_or_create(username=usernames, **kwargs)
    FACULTY_CACHE[fac_obj.username] = fac_obj

    return fac_obj
