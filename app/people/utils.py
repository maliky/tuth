# regex patterns to pull suffixes, prefixes, initials, etc.
import re

from django.contrib.auth import get_user_model

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
PREFIX_PATTERN = re.compile(r"\b(?:Dr|Mme|Mr|Prof|Rev|Sr|Fr)(?P<dot>\.)?(?(dot)\s*|\b)")
INITIAL_PATTERN = re.compile(r"\b([A-Z])(?P<dot>\.)?(?(dot)\s*|\b)")
FIRST_PATTERN = re.compile(r"^([A-Za-z-]+)")
LAST_PATTERN = re.compile(r"([A-Za-z-]+)$")


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

    # we harmonize dot for initial stuff
    raw_name = re.sub(r"\. *", ". ", raw_name)
    raw_name = re.sub(r",", " ", raw_name)

    m = re.match(FIRST_PATTERN, raw_name)
    if m:
        first_name = m.group(1)
        raw_name = raw_name[len(first_name) :].strip()

    m = re.search(LAST_PATTERN, raw_name)
    if m:
        last_name = m.group(1)
        raw_name = re.sub(LAST_PATTERN, "", raw_name).strip()
    return first_name, last_name, raw_name


def split_name(name: str) -> tuple[str, str, str, str, str]:
    """
    Splits a raw_name in prefix, first, middle, last, suffix
    Idealy the name's part are in logical order.
    but we try to take care of last before first
    or just last and initials for the first
    """
    name_suffix, raw_name = extract_suffix(name)
    name_prefix, raw_name = extract_prefix(raw_name)
    first_name, last_name, middle_name = extract_firstnlast(raw_name)
    return name_prefix, first_name, middle_name, last_name, name_suffix


def mk_username(first: str, last: str, unique=False, length: int = 13) -> str:
    """Generates a standard username. if unique is True make sure it is unique"""
    username_base = (first[:1] + last).lower()
    username = username_base[:length]

    if unique:
        counter = 1
        while User.objects.filter(username=username).exists():
            counter += 1
            username = f"{username_base}{counter}"

    return username
