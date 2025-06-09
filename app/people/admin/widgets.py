"""People.Admin.Widgets module."""

import re

from django.contrib.auth.models import User
from import_export import widgets

from app.academics.models import College
from app.people.models.profile import FacultyProfile
from app.shared.constants import TEST_PW


class UserWidget(widgets.ForeignKeyWidget):
    """
    Take a name and create a user with defaults
    """

    def __init__(self):
        super().__init__(User, field="username")

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

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"first_name": first, "last_name": last, "password": TEST_PW},
        )
        if created:
            user.set_password(TEST_PW)
            user.save()

        return user


class FacultyProfileWidget(widgets.ForeignKeyWidget):
    """
    Given a CSV cell containing something like
      "Dr. John A. Smith PhD"
    this widget will:
      • extract prefix ("Dr"), suffix ("PhD"), middle initials ("A")
      • extract first ("John") and last ("Smith")
      • create or retrieve a User(username=initials+".last") and FacultyProfile
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

    def __init__(self, college_field="college"):
        """
        college_field: name of the CSV column that holds the college code.
        """
        super().__init__(FacultyProfile, field="staff_id")
        self.college_field = college_field

    def clean(self, value, row=None, *args, **kwargs) -> FacultyProfile | None:
        if not value:
            return None

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
        college_code = (row.get(self.college_field) or "").strip()
        college, _ = College.objects.get_or_create(code=college_code)

        staff_id_value = f"TU-{uname.lower()}"
        # Create or retrieve FacultyProfile
        profile, _ = FacultyProfile.objects.get_or_create(
            user=user,
            defaults={"college": college, "staff_id": staff_id_value},
        )

        # Update profile fields
        updated = False
        if name_prefix and profile.name_prefix != name_prefix:
            profile.name_prefix = name_prefix
            updated = True
        if name_suffix and profile.name_suffix != name_suffix:
            profile.name_suffix = name_suffix
            updated = True
        if middle_name and profile.middle_name != middle_name:
            profile.middle_name = middle_name
            updated = True
        if updated:
            profile.save(update_fields=["name_prefix", "name_suffix", "middle_name"])

        return profile

    def render(self, value, obj=None) -> str:
        if not value:
            return ""
        return value.long_name
