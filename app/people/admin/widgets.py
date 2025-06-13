"""People.Admin.Widgets module."""

import re

from django.contrib.auth.models import User
from import_export import widgets

from app.academics.models import College
from app.people.models.profiles import Faculty, Staff
from app.shared.constants import TEST_PW

# regex patterns to pull suffixes, prefixes, initials, etc.
SUFFIX_PATTERNS = [
    r"\b(?:Ph\.?\s*D(?P<dot>\.)?)(?(dot)\s*|\b)",
    r"\b(?:Ed\.?\s*D(?P<dot>\.)?)(?(dot)\s*|\b)",
    r"\b(?:MD)\b",
    r"\b(?:SHF)\b",
    r"\b(?:(?:Jr|Sr)(?P<dot>\.)?)(?(dot)\s*|\b)",
    r"\b(?:I{1,3})\b",
]
PREFIX_PATTERN = r"\b(?:Dr|Mme|Mr|Prof|Rev|Sr|Fr)\.?\b"
INITIAL_PATTERN = r"\b([A-Z])\.?\b"
FIRST_PATTERN = r"^([A-Za-z-]+)"
LAST_PATTERN = r"([A-Za-z-]+)$"


def extract_suffix(value):
    name_suffix = ""
    for pat in SUFFIX_PATTERNS:
        m = re.search(pat, value, flags=re.IGNORECASE)
        if m:
            name_suffix = m.group(0).replace(".", "").upper()
            value = re.sub(pat, "", value, flags=re.IGNORECASE).strip()
            break
    return name_suffix, value


def extract_prefix(value):
    m = re.search(PREFIX_PATTERN, value)
    name_prefix = ""
    if m:
        name_prefix = m.group(0).replace(".", "")
        value = re.sub(PREFIX_PATTERN, "", value).strip()
    return name_prefix, value


def extract_firstnlast(value):
    # Extract first name
    first_name = ""
    last_name = ""

    m = re.match(FIRST_PATTERN, value)
    if m:
        first_name = m.group(1)
        value = value[len(first_name) :].strip()

    m = re.search(LAST_PATTERN, value)
    if m:
        last_name = m.group(1)
        value = re.sub(LAST_PATTERN, "", value).strip()
    return first_name, last_name, value


def _unique_usernrame(first_name, last_name, length=13):
    """
    Generating a unique username
    """
    uname_base = (first_name[:1] + last_name).lower()
    uname = uname_base[:length]
    counter = 1
    while User.objects.filter(username=uname).exists():
        counter += 1
        uname = f"{uname_base}{counter}"
    return uname


def _split_name(value):
    name_suffix, value = extract_suffix(value)
    name_prefix, value = extract_prefix(value)
    first_name, last_name, middle_name = extract_firstnlast(value)
    return name_prefix, first_name, middle_name, last_name, name_suffix


class StaffProfileWidget(widgets.ForeignKeyWidget):
    """
    “faculty”  ➜  User  ➜  Staff

    • expects the column value to be the full display name.
    • returns the *Staff* (not the User!) so foreign-keys can point to it.
    """

    def __init__(self):
        # > explain this,  Does it means to initiate a Staff instance ,
        super().__init__(Staff, field="staff_id")
        self._cache: dict[str, Staff] = {}

    def clean(self, value, row=None, *args, **kwargs) -> Staff | None:
        if not value:
            return None

        prefix, first, middle, last, suffix = _split_name(value)
        username = _unique_usernrame(first, last)

        if username in self._cache:
            return self._cache[username]

        user, _ = User.objects.get_or_create(
            username=username,
            defaults={
                "first_name": first.capitalize(),
                "last_name": last.capitalize(),
                "password": TEST_PW,
            },
        )

        staff, _ = Staff.objects.get_or_create(
            user=user,
            defaults={
                "name_prefix": prefix,
                "middle_name": middle,
                "name_suffix": suffix,
            },
        )
        self._cache[username] = staff
        return staff

    def render(self, value, obj=None) -> str:
        return value.long_name if value else ""  # type: ignore[no-any-return]

    def after_import(self, dataset, result, **kwargs):
        if kwargs.get("dry_run", False):
            self._cache.clear()


class FacultyWidget(widgets.ForeignKeyWidget):
    """
    Builds on StaffWidget: first get the Staff, then ensure a Faculty row exists.
    """

    def __init__(self):
        super().__init__(Faculty, field="id")

    def clean(self, value: str, row=None, *args, **kwargs) -> Faculty | None:
        staff = super().clean(value, row, *args, **kwargs)
        if staff is None:
            return None
        # pick the college code from the row (or a default)
        code = (row or {}).get("college_code", "COAS").strip().upper()
        college, _ = College.objects.get_or_create(code=code)

        faculty, _ = Faculty.objects.get_or_create(
            staff_profile=staff,
            defaults={"college": college},
        )
        return faculty
