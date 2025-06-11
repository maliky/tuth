"""People.Admin.Widgets module."""

import re

from django.contrib.auth.models import User
from import_export import widgets

from app.academics.models import College
from app.people.models.profile import FacultyProfile
from app.shared.constants import TEST_PW


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

    Given a CSV cell containing something like ``"Dr. John A. Smith PhD"`` this
    widget will:
      • extract prefix (``"Dr"``), suffix (``"PhD"``), middle initials (``"A"``)
      • extract first (``"John"``) and last (``"Smith"``)
      • create or retrieve a ``User`` and ``FacultyProfile`` record
    """

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

    def __init__(self, college_column="college_code"):
        """
        college_field: name of the CSV column that holds the college code.
        """
        super().__init__(FacultyProfile, field="staff_id")
        self.college_column = college_column
        self._cache: dict[str, FacultyProfile] = {}

    def clean(self, value, row=None, *args, **kwargs) -> FacultyProfile | None:
        if not value:
            return None

        key = f"{value.strip()}|{(row.get(self.college_column) or '').strip() if row else ''}"
        if key in self._cache:
            return self._cache[key]

        raw = value.strip()

        # Extract suffix
        name_suffix = ""
        for pat in self.SUFFIX_PATTERNS:
            m = re.search(pat, raw, flags=re.IGNORECASE)
            if m:
                name_suffix = m.group(0).replace(".", "").upper()
                raw = re.sub(pat, "", raw, flags=re.IGNORECASE).strip()
                break

        # Extract prefix
        m = re.search(self.PREFIX_PATTERN, raw)
        name_prefix = ""
        if m:
            name_prefix = m.group(0).replace(".", "")
            raw = re.sub(self.PREFIX_PATTERN, "", raw).strip()

        # Extract first name
        first_name = ""
        last_name = ""

        m = re.match(self.FIRST_PATTERN, raw)
        if m:
            first_name = m.group(1)
            raw = raw[len(first_name) :].strip()

        m = re.search(self.LAST_PATTERN, raw)
        if m:
            last_name = m.group(1)
            raw = re.sub(self.LAST_PATTERN, "", raw).strip()

        # Extract all middle name
        middle_name = raw

        # Build a username: use first letter(s) of first + last
        uname_base = (first_name[:1] + last_name).lower()
        uname = uname_base

        # in case we have several username similar
        counter = 1
        while User.objects.filter(username=uname).exists():
            counter += 1
            uname = f"{uname_base}{counter}"

        # Create or retrieve User
        user, created = User.objects.get_or_create(
            username=uname,
            defaults={
                "first_name": first_name.capitalize(),
                "last_name": last_name.capitalize(),
                "password": TEST_PW,
            },
        )
        if created:
            user.set_password(TEST_PW)
            user.save()

        # Determine college
        college_code = (row.get(self.college_column) or "").strip()
        college, _ = College.objects.get_or_create(code=college_code)

        staff_id_value = f"TU-{uname.lower()}"[:17]
        # Create or retrieve FacultyProfile
        facutly_profile, _ = FacultyProfile.objects.get_or_create(
            user=user,
            defaults={"college": college, "staff_id": staff_id_value},
        )

        # Update profile fields
        updated = False
        if name_prefix:
            facutly_profile.name_prefix = name_prefix
            updated = True
        if name_suffix:
            facutly_profile.name_suffix = name_suffix
            updated = True
        if middle_name:
            facutly_profile.middle_name = middle_name
            updated = True
        if updated:
            facutly_profile.save(
                update_fields=["name_prefix", "name_suffix", "middle_name"]
            )

        self._cache[key] = facutly_profile
        return facutly_profile

    def render(self, value, obj=None) -> str:
        if not value:
            return ""
        return value.long_name  # type: ignore[no-any-return]
