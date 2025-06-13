"""People.Admin.Widgets module."""

import re

from django.contrib.auth.models import User
from import_export import widgets

from app.academics.models import College
from app.people.models.profile import FacultyProfile
from app.shared.constants import TEST_PW

# regex patterns to pull suffixes, prefixes, initials, etc.
SUFFIX_PATTERNS = [
    r"\b(?:Ph\.?\s*D(?P<dot>\.)?)(?(dot)\s*|\b)",
    r"\b(?:Ed\.?\s*D(?P<dot>\.)?)(?(dot)\s*|\b)",
    r"\b(?:MD)\b",
    r"\b(?:SHF)\b",
    r"\b(?:(?:Jr|Sr)(?P<dot>\.)?)(?(dot)\s*|\b)",
    r"\b(?:I{1,3})\b",
    # r"\bPh\.?\s*[Dd]\.?\b",
    # r"\bEd\.?\s*[Dd]\.?\b",
    # r"\bMD\b",
    # r"\bSHF\b",
    # r"\b(?:Jr|Sr)\.?\b",
    # r"\bI{1,3}\b",
]
PREFIX_PATTERN = r"\b(?:Dr|Mme|Mr|Prof|Rev|Sr|Fr)\.?\b"
INITIAL_PATTERN = r"\b([A-Z])\.?\b"
# first and last assume word characters or hyphen
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


def make_unique_username(first_name, last_name, length=13):
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


class UserWidget(widgets.ForeignKeyWidget):
    """Create or lookup :class:`User` instances with basic defaults.

    The widget keeps an internal cache so repeated calls with the same name do
    not hit the database again.
    """

    def __init__(self):
        super().__init__(User, field="username")
        self._cache: dict[str, User] = {}

    def clean(self, value, row=None, *args, **kwargs) -> User | None:
        if not value:
            return None

        parts = value.split()
        if not parts:
            raise ValueError("name cannot be empty")

        first = parts[0]
        last = parts[-1]
        initials = "".join(p[0] for p in parts[:-1]) or first[0]
        username = f"{initials}{last}".lower()

        if username in self._cache:
            return self._cache[username]

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"first_name": first, "last_name": last, "password": TEST_PW},
        )
        if created:
            user.set_password(TEST_PW)
            user.save()

        self._cache[username] = user
        return user


class FacultyProfileWidget(widgets.ForeignKeyWidget):
    """Parse a full name and return a ``FacultyProfile`` instance.

    The widget caches lookups so identical rows don't trigger multiple database
    queries.
    need college code

    Given a CSV cell containing something like ``"Dr. John A. Smith PhD"`` this
    widget will:
      • extract prefix (``"Dr"``), suffix (``"PhD"``), middle initials (``"A"``)
      • extract first (``"John"``) and last (``"Smith"``)
      • create or retrieve a ``User`` and ``FacultyProfile`` record
    """

    def __init__(self):
        """
        college_field: name of the CSV column that holds the college code.
        """
        super().__init__(FacultyProfile, field="staff_id")
        self._cache: dict[str, FacultyProfile] = {}

    def clean(self, value, row=None, *args, **kwargs) -> FacultyProfile | None:

        assert value, f"value {value} should not be empty or None"
        raw_value = value.strip()

        name_suffix, raw_value = extract_suffix(raw_value)
        name_prefix, raw_value = extract_prefix(raw_value)
        first_name, last_name, middle_name = extract_firstnlast(raw_value)

        uname = make_unique_username(first_name=first_name, last_name=last_name)

        if uname in self._cache:
            return self._cache[uname]

        # Create or retrieve User
        user, user_created = User.objects.get_or_create(
            username=uname,
            defaults={
                "first_name": first_name.capitalize(),
                "last_name": last_name.capitalize(),
                "password": TEST_PW,
            },
        )
        if user_created:
            user.set_password(TEST_PW)
            user.save()

        college_code = row.get("college_code", "COAS").strip()

        if not college_code:
            college_code = "COAS"

        college, college_created = College.objects.get_or_create(code=college_code)

        if college_created:
            college.save()

        faculty_profile, faculty_created = FacultyProfile.objects.get_or_create(
            user=user,
            defaults={
                "college": college,
                "staff_id": f"TU-{uname}",
                "name_suffix": name_suffix,
                "name_prefix": name_prefix,
                "middle_name": middle_name,
            },
        )
        if faculty_created:
            faculty_profile.save()

        self._cache[uname] = faculty_profile
        return faculty_profile

    def render(self, value, obj=None) -> str:
        if not value:
            return ""
        return value.long_name  # type: ignore[no-any-return]

    def after_import(self, dataset, result, **kwargs):
        if kwargs.get("dry_run", False):
            self._cache.clear()
