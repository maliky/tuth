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

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Hashable, Optional, Sequence, TypeVar, Tuple

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rapidfuzz.distance import JaroWinkler

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

PREFIX_PATTERN = re.compile(
    r"(\b(?:Doc|Dr|Hon|Mme|Mrs?|Ms|Prof|Rev|Sr|Fr)(?P<dot>\.)?(?(dot)\s*|\b))+",
    re.IGNORECASE,
)
FULL_INITIAL_PATTERN = re.compile(r"\b([A-Z])(?P<dot>\.)?(?(dot)\s*|\b)")
FIRST_PATTERN = re.compile(r"^([A-Za-z-]+|[A-Za-z-]\.?)")
LAST_PATTERN = re.compile(r"([A-Za-z-]+)$")
INITIAL_PATTERN = re.compile(r"\b([A-Z])(?=\s|$|\.)")

USERNAME_PREFIX_LEN_DFT = 20
USERNAME_SEP_DFT = "."

@dataclass
class NameParts:
    """Parsed representation of a raw name suitable for user defaults."""

    prefix: str
    first: str
    middle: str
    last: str
    suffix: str

    def to_dict(self) -> dict[str, str]:
        """Return admin-friendly defaults derived from the parsed name."""
        return {
            "first_name": self.first.capitalize(),
            "last_name": self.last.capitalize(),
            "name_prefix": self.prefix,
            "middle_name": self.middle,
            "name_suffix": self.suffix,
        }

    def to_string(self) -> str:
        """Return the full name as a string."""
        return " ".join(self.parts())

    def parts(self) -> Tuple[str, str, str, str, str]:
        """Returns the Name parts."""
        return (self.prefix, self.first, self.middle, self.last, self.suffix)


def default_password(first: str, last: str) -> str:
    """Return the canonical password used when creating new profiles."""
    return mk_password(first, last)


Entity = TypeVar("Entity")


def cached_entity(
    cache: Dict[Hashable, Entity],
    key: Hashable,
    factory: Callable[[], Entity],
) -> Entity:
    """Return a cached entity, computing it only once per key."""
    if key not in cache:
        cache[key] = factory()
    return cache[key]


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
    repeating_initials = r"([A-Z](\s|\b))*"
    back_m = re.match(repeating_initials, back_part)
    if not back_m:
        return raw_name
    back_match = back_m.group(0)
    if back_match != back_part:
        return raw_name
    return f"{back_part} {front_part}"


def extract_firstnlast(raw_name: str) -> tuple[str, str, str]:
    """Extract the first and last parts of a name."""
    first_name = ""
    last_name = ""
    raw_name = re.sub(r"\. *", " ", raw_name)
    raw_name = inverse_if_comma(raw_name).strip()
    raw_name = inverse_if_initial_last(raw_name).strip()

    m = re.match(FIRST_PATTERN, raw_name)
    if m:
        first_name = m.group(1)
        raw_name = raw_name[len(first_name) :].strip()

    m = re.search(LAST_PATTERN, raw_name)
    if m:
        last_name = m.group(1)
        raw_name = re.sub(LAST_PATTERN, "", raw_name).strip()

    raw_name = re.sub(r"\b(\w)\b", r"\1.", raw_name).strip()
    if not last_name and not raw_name:
        return last_name, first_name, raw_name

    return first_name, last_name, raw_name


def handle_numbered_name_suffix(last_name, name_suffix):
    """Concatenate any roman numeral from the suffix in the last_name."""
    pat = r"\b(?:I{1,3})\b(?:,|\.)?"
    m = re.search(pat, name_suffix)
    if m:
        name_suffix = re.sub(pat, "", name_suffix)
        last_name += re.sub(r"\.|,", "", m.group()).strip()
    return last_name, name_suffix


def parse_name(
    raw: str | None, *, fallback_first: str = "Default", fallback_last: str = "User"
) -> NameParts:
    """Split a name and fill sensible defaults for missing parts."""
    _n = split_name(raw or "")
    return NameParts(
        prefix=_n.prefix,
        first=_n.first or fallback_first,
        middle=_n.middle,
        last=_n.last or fallback_last,
        suffix=_n.suffix,
    )


def split_name(name: str) -> NameParts:
    """Splits a raw_name in prefix, first, middle, last, suffix."""
    name_suffix, raw_name = extract_suffix(name)
    name_prefix, raw_name = extract_prefix(raw_name)
    first_name, last_name, middle_name = extract_firstnlast(raw_name)
    first_name, middle_name, last_name = [
        n.replace(".", "").strip() for n in [first_name, middle_name, last_name]
    ]
    first, middle, last_name = [
        re.sub(INITIAL_PATTERN, r"\1.", n) for n in [first_name, middle_name, last_name]
    ]
    prefix = re.sub(PREFIX_PATTERN, r"\1.", name_prefix)
    last, suffix = handle_numbered_name_suffix(last_name, name_suffix)
    return NameParts(prefix=prefix, first=first, middle=middle, last=last, suffix=suffix)


def mk_username(
    first: str,
    last: str,
    middle: str = "",
    unique: Optional[bool] = False,
    exclude: Optional[set[str]] = None,
    prefix_len: Optional[int] = None,
    sep: Optional[str] = None,
) -> str:
    """
    Generates a username after cleaning the names.

    first prefix len + middle initial . last.
    """
    middle_initial = re.sub(r"\.| |-", "", middle)[:1]
    first = re.sub(r"-|\.| ", "", first)
    last = re.sub(r"-|\.| ", "", last)
    prefix_len = USERNAME_PREFIX_LEN_DFT if prefix_len is None else prefix_len
    sep = USERNAME_SEP_DFT if sep is None else sep
    exclude = set() if exclude is None else exclude

    baseusername = (first[:prefix_len] + middle_initial + sep + last).lower()
    username = baseusername
    if unique:
        counter = 1
        while User.objects.filter(username=username).exists():
            counter += 1
            username = f"{baseusername}{counter}"
    if exclude:
        counter = 1
        while len({username} - exclude) == 0:
            counter += 1
            username = f"{baseusername}{counter}"
    return username


def extract_id_num(user_id: str) -> int:
    """Extract the number of an user_id what ever the prefix."""
    m = re.match(r".*?([0-9]+)", user_id)
    if m is None:
        raise ValidationError(f"A user id should have some digits in it. {user_id}")
    return int(m.groups(0)[0])


def get_default_user():
    """Returns a dummy User."""
    d_user, created = User.objects.get_or_create(
        username="default_user",
        defaults={
            "first_name": "Default",
            "last_name": "User",
        },
    )
    if created:
        d_user.set_unusable_password()
        d_user.save(update_fields=["password"])
    return d_user


def photo_upload_to(instance, filename: str) -> str:
    """Store uploads under photos/<model>/<user-id>/<filename>."""
    _class = instance.__class__.__name__.lower()
    return str(Path("photos") / _class / str(instance.user_id) / filename)


def mk_password(first: str, last: str) -> str:
    """Make a very simple password from the first and last name of a user."""
    a_token = "A" if not first else first[0].upper()
    b_token = "B" if not last else last[0].upper()
    return f"{a_token}-pass-{b_token}!"


def canonicalize_name(raw: str) -> str:
    """Return a canonical username-like representation of a name."""
    return split_name(raw).to_string()


def name_distance(name_a: str, name_b: str, *, prefix_weight: float = 0.1) -> float:
    """Return a normalized distance (0=identical, 1=different) between two names."""
    canonical_a = canonicalize_name(name_a)
    canonical_b = canonicalize_name(name_b)
    return float(
        JaroWinkler.normalized_distance(
            canonical_a, canonical_b, prefix_weight=prefix_weight
        )
    )


def names_match(name_a: str, name_b: str, *, threshold: float = 0.2, **kwargs) -> bool:
    """Return True when the distance between two names is within a given threshold."""
    return name_distance(name_a, name_b, **kwargs) <= threshold


def name_similarity_matrix(
    left_names: Sequence[str],
    right_names: Sequence[str],
    *,
    max_distance: float | None = None,
    **kwargs,
) -> list[dict[str, object]]:
    """Return a list of similarity rows describing pairwise name distances."""
    matrix: list[dict[str, object]] = []
    for left in left_names:
        for right in right_names:
            dist = name_distance(left, right, **kwargs)
            if max_distance is not None and dist > max_distance:
                continue
            matrix.append({"left": left, "right": right, "distance": dist})
    return matrix
