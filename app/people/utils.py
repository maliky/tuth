"""Name-parsing utilities.

This module exposes helper functions for parsing a person's name into
its component parts and for generating usernames. Each helper focuses on
extracting a specific portion of a name, allowing the caller to split a
raw string into prefix, first name, middle name, last name and suffix.

Functions:
    extract_suffix(raw_name): Return any suffix (e.g., "Jr", "PhD") and
        the remaining text.
    extract_prefix(raw_name): Return any prefix (e.g., "Dr", "Prof") and
        the remaining text.
    inverse_if_comma(raw_name): Swap comma-separated name segments.
    extract_firstnlast(raw_name): Identify first and last name elements.
    split_name(name): Split a name into prefix, first, middle, last and
        suffix parts.
    mk_username(first, last, unique=False, length=13): Create a standard
        username from the provided names.
"""

# regex patterns to pull suffixes, prefixes, initials, etc.
import re

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()


SUFFIX_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(?:Ph\.?\s*D(?P<dot>\.)?)(?(dot)\s*|\b)",
        r"\b(?:Ed\.?\s*D(?P<dot>\.)?)(?(dot)\s*|\b)",
        r"\b(?:MD)\b",
        r"\b(?:SHF)\b",
        r"\b(?:(?:Jr|Sr)(?P<dot>\.)?)(?(dot)\s*|\b)",
        r"\b(?:I{1,3})\b",
    ]
]

# prefix if followed by a dot then has a space just after
PREFIX_PATTERN = re.compile(
    r"(\b(?:Doc|Dr|Mme|Mrs?|Ms|Prof|Rev|Sr|Fr)(?P<dot>\.)?(?(dot)\s*|\b))+", re.IGNORECASE
)
# A single letter folowed by a dot and a space or a word separatore '\b'
FULL_INITIAL_PATTERN = re.compile(r"\b([A-Z])(?P<dot>\.)?(?(dot)\s*|\b)")

# A sequence of small letters and cap optionaly separated with dots at the start of a string
FIRST_PATTERN = re.compile(r"^([A-Za-z-]+|[A-Za-z-]\.?)")

# At least one letter small or cap at the end of the string
LAST_PATTERN = re.compile(r"([A-Za-z-]+)$")

# A single letter follow by a space or the end of a string or a dot
INITIAL_PATTERN = re.compile(r"\b([A-Z])(?=\s|$|\.)")


def extract_suffix(raw_name: str) -> tuple[str, str]:
    """Extract the suffix of a name."""
    name_suffix = ""
    for pat in SUFFIX_PATTERNS:
        m = re.search(pat, raw_name)
        if m:
            name_suffix = m.group(0).replace(".", "").strip()
            raw_name = re.sub(pat, "", raw_name).strip()
            break
    return name_suffix, raw_name


def extract_prefix(raw_name: str) -> tuple[str, str]:
    """Extracts the prefix of a name."""
    m = re.search(PREFIX_PATTERN, raw_name)
    name_prefix = ""
    if m:
        name_prefix = m.group(0).replace(".", "").strip()
        raw_name = re.sub(PREFIX_PATTERN, "", raw_name).strip()
    return name_prefix, raw_name


def inverse_if_comma(raw_name: str) -> str:
    """Reverse the parts separated by a comma eg. A, B -> B, A."""
    parts = raw_name.split(",")
    return " ".join([p for p in parts[::-1]])


def inverse_if_initial_last(raw_name: str) -> str:
    """Reverse the parts if the second is made only of initials."""
    front_part, _, back_part = raw_name.partition(" ")
    # front_m = re.match(INITIAL_PATTERN, front_part)

    REPEATING_INITIALS = r"([A-Z](\s|\b))*"
    back_m = re.match(REPEATING_INITIALS, back_part)
    if not back_m:
        return raw_name

    back_match = back_m.group(0)
    if back_match != back_part:
        return raw_name
    return f"{back_part} {front_part}"


def extract_firstnlast(raw_name: str) -> tuple[str, str, str]:
    """Extracts the first and last parts of a name."""
    first_name = ""
    last_name = ""
    # Before we simply map the first -> first and last -> last
    # We try to enforce the following rule.
    # if only one name is there, it is the last
    # if two parts are there, and one is 2 or less char,
    # we take is as initial of first name.
    # else standard first middle last

    # We remove extra spaces after dots
    # raw_name = re.sub(r"\. *", ". ", raw_name)

    # remove all dots
    raw_name = re.sub(r"\. *", " ", raw_name)

    # if we have a comma, inverse first and last
    raw_name = inverse_if_comma(raw_name).strip()
    # if we have 2 parts made of initial only then must be first names
    raw_name = inverse_if_initial_last(raw_name).strip()

    m = re.match(FIRST_PATTERN, raw_name)
    if m:
        # ? why group(1) and not group(0). investigate and clarify even if no diff.
        first_name = m.group(1)
        raw_name = raw_name[len(first_name) :].strip()

    m = re.search(LAST_PATTERN, raw_name)
    if m:
        last_name = m.group(1)
        raw_name = re.sub(LAST_PATTERN, "", raw_name).strip()

    # removing any trailing dots
    # raw_name = re.sub(r"^\.", "", raw_name).strip()

    # Harmonizing dots to initials
    raw_name = re.sub(r"\b(\w)\b", r"\1.", raw_name).strip()
    if not last_name and not raw_name:  # so if only first_name
        # first_name -> last name
        return last_name, first_name, raw_name

    return first_name, last_name, raw_name


def split_name(name: str) -> tuple[str, str, str, str, str]:
    """Splits a raw_name in prefix, first, middle, last, suffix.

    Idealy the name's part are in logical order.
    but we try to take care of last before first
    or just last and initials for the first.
    """
    name_suffix, raw_name = extract_suffix(name)
    name_prefix, raw_name = extract_prefix(raw_name)
    first_name, last_name, middle_name = extract_firstnlast(raw_name)

    # we remove all the dots from the names.
    first_name, middle_name, last_name = [
        n.replace(".", "").strip() for n in [first_name, middle_name, last_name]
    ]

    # Restore dots to single letters only
    first_name, middle_name, last_name = [
        re.sub(INITIAL_PATTERN, r"\1.", n) for n in [first_name, middle_name, last_name]
    ]

    # Restore dots on prefixes
    name_prefix = re.sub(PREFIX_PATTERN, r"\1.", name_prefix)
    return name_prefix, first_name, middle_name, last_name, name_suffix


def mk_username(
    first: str, last: str, unique=False, max_length: int = 0, student_scheme=False
) -> str:
    """Generates a standard username.

    If unique is True make sure it is unique.
    The default rule is to take the first 2 char of the first name
    and concatenate them with the last name. All lowercase.
    but if student_scheme is True, take the first.lastname as username
    - maxlength 13 char
    """
    if not student_scheme:
        username_base = (first[:2] + last).lower()
    else:
        username_base = f"{first}.{last}".lower()

    username = username_base[:max_length] if max_length else username_base

    if unique:
        counter = 1
        while User.objects.filter(username=username).exists():
            counter += 1
            username = f"{username_base}{counter}"

    return username


def extract_id_num(user_id: str) -> int:
    """Extract the number of an user_id what ever the prefix."""
    # using non greedy start
    m = re.match(r".*?([0-9]+)", user_id)

    if m is None:
        raise ValidationError(f"A user id should have some digits in it. {user_id}")

    # the group cannot be something else than digits
    return int(m.groups(0)[0])
