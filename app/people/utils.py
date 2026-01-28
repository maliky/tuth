"""Name-parsing utilities.

This module provides helpers for parsing a person's name into parts and
for generating usernames from those parts.

Functions:
    extract_suffix(raw_name): Return any suffix and the remaining text.
    extract_prefix(raw_name): Return any prefix and the remaining text.
    inverse_if_comma(raw_name): Swap comma-separated name segments.
    extract_firstnlast(raw_name): Identify first and last name elements.
    split_name(name): Split a name into prefix, first, middle, last, suffix.
    mk_username(first, last, middle, unique, exclude, prefix_len, sep):
        Create a standard username from the provided names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Hashable,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    cast,
)

from app.people.constants import USER_KWARGS
from app.shared.types import _T, ModelT

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db.models.manager import BaseManager
from rapidfuzz.distance import JaroWinkler

from app.shared.utils import get_in_row

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
    """Parsed representation of a raw name for user defaults.

    Stores prefix, first, middle, last, and suffix parts with helpers
    for formatting and serialization.
    """

    prefix: str
    first: str
    middle: str
    last: str
    suffix: str

    # def __str__(self):
    #     return self.to_string(full=True)
    def _ensure_capitalize(self) -> None:
        """Capitalize name parts in place for display.

        This mutates the instance fields and leaves the suffix unchanged.
        """
        # do not capitalize "suffix"
        self.prefix = self.prefix.title()
        self.first = self.first.title()
        self.middle = self.middle.title()
        self.last = self.last.upper()
        # leave suffix as is.

    def to_dict(self, full=True) -> dict[str, str]:
        """Return admin-friendly defaults derived from the parsed name.

        Args:
            full: Include prefix, middle, and suffix in the result.

        Returns:
            Name fields keyed as prefix_name, last_name, and so on.
        """
        self._ensure_capitalize()
        named_parts = ["first", "last"]
        if full:
            named_parts += ["prefix", "middle", "suffix"]

        return {f"{np}_name": getattr(self, np, "") for np in named_parts}

    def to_string(self, full=True) -> str:
        """Return the name as a string.

        Args:
            full: Include prefix and suffix when building the string.

        Returns:
            Joined name parts with empty segments removed.
        """
        self._ensure_capitalize()
        _parts = self.fullparts() if full else self.parts()
        return " ".join([p for p in _parts if p])

    def parts(self) -> Tuple[str, str, str]:
        """Return first, last, and middle name parts in that order.

        Returns:
            First, last, and middle name parts.
        """
        self._ensure_capitalize()
        return (self.first, self.last, self.middle)

    def fullparts(self) -> Tuple[str, str, str, str, str]:
        """Return prefix, first, middle, last, and suffix in that order.

        Returns:
            Prefix, first, middle, last, and suffix parts.
        """
        self._ensure_capitalize()
        return (self.prefix, self.first, self.middle, self.last, self.suffix)


def cached_entity(
    cache: Dict[Hashable, _T],
    key: Hashable,
    factory: Callable[[], _T],
) -> _T:
    """Return a cached entity, computing it only once per key.

    Args:
        cache: Cache store used to keep entities by key.
        key: Lookup key for the cache.
        factory: Function used to build the entity when missing.

    Returns:
        Cached or newly created entity.
    """
    if key not in cache:
        cache[key] = factory()
    return cache[key]


def extract_suffix(raw_name: str) -> tuple[str, str]:
    """Extract a name suffix and return the remaining text.

    Args:
        raw_name: Raw name string to inspect.

    Returns:
        Suffix and remaining name.

    Examples:
        "Dr Jane Doe Jr" yields suffix "Jr" and remaining "Dr Jane Doe".
    """
    name_suffix = ""
    for pat in SUFFIX_PATTERNS:
        m = re.search(pat, raw_name)
        if m:
            name_suffix = m.group(0).replace(".", "").strip()
            raw_name = re.sub(pat, "", raw_name).strip()
            break
    return name_suffix, raw_name


def extract_prefix(raw_name: str) -> tuple[str, str]:
    """Extract a name prefix and return the remaining text.

    Args:
        raw_name: Raw name string to inspect.

    Returns:
        Prefix and remaining name.
    """
    m = re.search(PREFIX_PATTERN, raw_name)
    prefix_name = ""
    if m:
        prefix_name = m.group(0).replace(".", "").strip()
        raw_name = re.sub(PREFIX_PATTERN, "", raw_name).strip()
    return prefix_name, raw_name


def inverse_if_comma(raw_name: str) -> str:
    """Reverse comma-separated parts in a name.

    Args:
        raw_name: Raw name string to inspect.

    Returns:
        Name string with comma-separated parts reversed.

    Examples:
        "Doe, Jane" becomes "Jane Doe".
    """
    parts = raw_name.split(",")
    return " ".join([p for p in parts[::-1]])


def inverse_if_initial_last(raw_name: str) -> str:
    """Reverse the parts when the trailing segment is initials only.

    Args:
        raw_name: Raw name string to inspect.

    Returns:
        Name string with parts reversed when the second segment is initials.
    """
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
    """Extract the first and last parts of a name.

    Args:
        raw_name: Raw name string to inspect.

    Returns:
        First name, last name, and remaining text.
    """
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


def handle_numbered_suffix(last_name, name_suffix):
    """Concatenate any roman numeral from the suffix into the last name.

    Args:
        last_name: Last name portion to update.
        name_suffix: Suffix string to inspect and trim.

    Returns:
        Updated (last_name, name_suffix) pair.

    Examples:
        ("Smith", "II") yields ("Smith-II", "").
    """
    pat = r"\b(?:I{1,3})\b(?:,|\.)?"
    m = re.search(pat, name_suffix)
    if m:
        name_suffix = re.sub(pat, "", name_suffix)
        last_name += "-" + re.sub(r"\.|,", "", m.group()).strip()
    return last_name, name_suffix


def parse_name(
    raw: str | None, *, fallback_first: str = "Default", fallback_last: str = "User"
) -> NameParts:
    """Split a name and fill missing parts with fallback values.

    Args:
        raw: Raw name string to parse.
        fallback_first: Value used when the first name is missing.
        fallback_last: Value used when the last name is missing.

    Returns:
        Parsed name parts with fallbacks applied.

    Examples:
        "Ada" yields first name "Ada" and uses fallback_last for last name.
    """
    _n = split_name(raw or "")
    return NameParts(
        prefix=_n.prefix,
        first=_n.first or fallback_first,
        middle=_n.middle,
        last=_n.last or fallback_last,
        suffix=_n.suffix,
    )


def split_name(name: str) -> NameParts:
    """Split a raw name into prefix, first, middle, last, and suffix.

    Args:
        name: Raw name string to parse.

    Returns:
        Parsed name parts.
    """
    suffix, raw = extract_suffix(name)
    prefix, raw = extract_prefix(raw)
    first, last, middle = extract_firstnlast(raw)
    first, middle, last = [n.replace(".", "").strip() for n in [first, middle, last]]
    first, middle, last = [
        re.sub(INITIAL_PATTERN, r"\1.", n) for n in [first, middle, last]
    ]
    prefix = re.sub(PREFIX_PATTERN, r"\1.", prefix)
    last, suffix = handle_numbered_suffix(last, suffix)
    return NameParts(prefix=prefix, first=first, middle=middle, last=last, suffix=suffix)


def mk_fullusername(
    fullname: str,
    unique: Optional[bool] = False,
    exclude: Optional[set[str]] = None,
    prefix_len: Optional[int] = None,
    sep: Optional[str] = None,
) -> str:
    """Generate a username from a full name string.

    Args:
        fullname: Full name to parse into components.
        unique: When set, ensure the username is not already used by checking users.
        exclude: Usernames to avoid when checking uniqueness.
        prefix_len: Limit for the first-name portion of the username.
        sep: Requested separator between name parts; this helper always uses ".".

    Returns:
        Generated username string.

    Examples:
        "Ada Lovelace" yields "ada.lovelace".
    """
    _n = split_name(fullname)
    return mk_username(
        _n.first,
        _n.last,
        _n.middle,
        unique=unique,
        exclude=exclude,
        prefix_len=prefix_len,
        sep=".",
    )


def mk_username(
    first: str,
    last: str,
    middle: str = "",
    unique: Optional[bool] = False,
    exclude: Optional[set[str]] = None,
    prefix_len: Optional[int] = None,
    sep: Optional[str] = None,
) -> str:
    """Generate a username after cleaning the name parts.

    Args:
        first: First name used for the username prefix.
        last: Last name used for the username suffix.
        middle: Middle name used to derive the middle initial.
        unique: When set, ensure the username is not already used by checking users.
        exclude: Usernames to avoid when checking uniqueness.
        prefix_len: Limit for the first-name portion of the username.
        sep: Separator inserted between name parts.

    Returns:
        Generated username string.

    Examples:
        ("Ada", "Lovelace") yields "ada.lovelace".
    """
    middle_initial = re.sub(r"\.| |-", "", middle)[:1]
    first = re.sub(r"-|\.| ", "", first)
    last = re.sub(r"-|\.| ", "", last)
    prefix_len = USERNAME_PREFIX_LEN_DFT if prefix_len is None else prefix_len
    sep = USERNAME_SEP_DFT if sep is None else sep
    exclude = set() if exclude is None else exclude

    baseusername = (
        first[:prefix_len] + middle_initial + (sep if first else "") + last
    ).lower()
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
    """Extract the numeric portion of a user id string.

    Args:
        user_id: Raw identifier string to inspect.

    Returns:
        Extracted numeric value.

    Raises:
        ValidationError: If no digits are present in the identifier.

    Examples:
        "TU-00123" yields 123.
    """
    m = re.match(r".*?([0-9]+)", user_id)
    if m is None:
        raise ValidationError(f"A user id should have some digits in it. {user_id}")
    return int(m.groups(0)[0])


def get_default_user():
    """Return or create the default user record.

    Returns:
        Default user with an unusable password when newly created.
    """
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
    """Build the upload path for a person's photo.

    Args:
        instance: Model instance with a user_id attribute.
        filename: Original file name.

    Returns:
        Relative path under photos/<model>/<user-id>/<filename>.
    """
    _class = instance.__class__.__name__.lower()
    return str(Path("photos") / _class / str(instance.user_id) / filename)


def mk_password(first: str, last: str) -> str:
    """Build a simple password from first and last names.

    Args:
        first: First name used for the first initial.
        last: Last name used for the last initial.

    Returns:
        Password string in the A-pass-B! pattern.

    Examples:
        ("Ada", "Lovelace") yields "A-pass-L!".
    """
    a_token = "A" if not first else first[0].upper()
    b_token = "B" if not last else last[0].upper()
    return f"{a_token}-pass-{b_token}!"


def canonicalize_name(raw: str) -> str:
    """Return a canonical representation of a name string.

    Args:
        raw: Raw name string to normalize.

    Returns:
        Canonicalized name string.
    """
    return split_name(raw).to_string()


def name_distance(name_a: str, name_b: str, *, prefix_weight: float = 0.1) -> float:
    """Return a normalized distance between two names.

    Args:
        name_a: First name string.
        name_b: Second name string.
        prefix_weight: Weight given to prefix similarity.

    Returns:
        Distance value where 0 is identical and 1 is different.

    Examples:
        Identical names yield 0.0.
    """
    canonical_a = canonicalize_name(name_a)
    canonical_b = canonicalize_name(name_b)
    return float(
        JaroWinkler.normalized_distance(
            canonical_a, canonical_b, prefix_weight=prefix_weight
        )
    )


def names_match(name_a: str, name_b: str, *, threshold: float = 0.2, **kwargs) -> bool:
    """Return True when the distance between two names is within a threshold.

    Args:
        name_a: First name string.
        name_b: Second name string.
        threshold: Maximum distance allowed for a match.
        **kwargs: Options forwarded to name_distance.

    Returns:
        True when the names are similar enough, otherwise False.
    """
    return name_distance(name_a, name_b, **kwargs) <= threshold


def name_similarity_matrix(
    left_names: Sequence[str],
    right_names: Sequence[str],
    *,
    max_distance: float | None = None,
    **kwargs,
) -> list[dict[str, object]]:
    """Return similarity rows describing pairwise name distances.

    Args:
        left_names: Names to compare on the left.
        right_names: Names to compare on the right.
        max_distance: When set, skip pairs beyond this distance.
        **kwargs: Options forwarded to name_distance.

    Returns:
        Similarity rows with left, right, and distance fields.
    """
    matrix: list[dict[str, object]] = []
    for left in left_names:
        for right in right_names:
            dist = name_distance(left, right, **kwargs)
            if max_distance is not None and dist > max_distance:
                continue
            matrix.append({"left": left, "right": right, "distance": dist})
    return matrix


def get_name_parts(row) -> Tuple[Dict[str, Any], str, str]:
    """Extract name parts from a row.

    Args:
        row: Row data containing *_name fields.

    Returns:
        Three values: parts, first_name, and last_name.
    """
    _d = {
        f"{k}_name": get_in_row(f"{k}_name", row)
        for k in ("prefix", "first", "middle", "last", "suffix")
    }
    return _d, _d["first_name"], _d["last_name"]


def name_parts_from_row(
    row: Mapping[str, str | None] | None,
    *,
    fullname_key: str = "long_name",
    raw_name: str | None = None,
    fallback_first: str = "",
    fallback_last: str = "",
) -> NameParts:
    """Return parsed name parts from row fields.

    Row-provided parts are used when a last name is present; otherwise the
    full name is parsed.

    Args:
        row: Row data containing name fields.
        fullname_key: Field name used to read a full name when parts are missing.
        raw_name: Explicit full name string to parse when provided.
        fallback_first: Value used when the first name is missing.
        fallback_last: Value used when the last name is missing.

    Returns:
        Parsed name parts derived from the row or the full name string.
    """
    safe_row = row or {}
    prefix = get_in_row("prefix_name", safe_row)
    first = get_in_row("first_name", safe_row)
    middle = get_in_row("middle_name", safe_row)
    last = get_in_row("last_name", safe_row)
    suffix = get_in_row("suffix_name", safe_row)

    if last:
        return NameParts(prefix, first, middle, last, suffix)

    source_name = raw_name or get_in_row(fullname_key, safe_row)
    return parse_name(
        source_name,
        fallback_first=fallback_first,
        fallback_last=fallback_last,
    )


def create_person_factory(
    username: str,
    model: type[ModelT],
    dfts: dict[str, Any],
    user_getter: Callable[[ModelT], AbstractBaseUser],
) -> Callable[[], ModelT]:
    """Return a factory that creates or fetches a person record.

    The factory uses get_or_create and sets a password on the related user
    when a new record is created.

    Args:
        username: Username used for get_or_create.
        model: Model used to create the person record.
        dfts: Default field values used when creating the record.
        user_getter: Function that returns the related user object.

    Returns:
        Factory function that returns the person record.
    """

    def f() -> ModelT:

        manager = cast(BaseManager[ModelT], model._default_manager)

        pers, _created = manager.get_or_create(username=username, defaults=dfts)

        user = user_getter(pers)
        if _created:
            _pwd = mk_password(dfts["first_name"], dfts["last_name"])
            user.set_password(_pwd)
            user.save(update_fields=["password"])

        return pers

    return f


def get_name(**kwargs) -> NameParts:
    """Extract name parts from keyword arguments.

    Args:
        **kwargs: Keyword arguments containing *_name fields.

    Returns:
        Parsed name parts.
    """
    named_parts = ["prefix", "first", "middle", "last", "suffix"]
    parts = {np: kwargs.get(f"{np}_name", "") for np in named_parts}
    return NameParts(**parts)


def split_kwargs(**kwargs) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Split keyword arguments into user fields and remaining person fields.

    Args:
        **kwargs: Keyword arguments to split.

    Returns:
        Two groups: user_kwargs and person_kwargs.
    """
    user_kwargs = {k: kwargs.pop(k) for k in list(kwargs) if k in USER_KWARGS}
    return user_kwargs, kwargs


def get_full_name(person: Any) -> str:
    """Return the full name for a person.

    Args:
        person: Object with name fields and a related user when available.

    Returns:
        Full name assembled from prefix, first, middle, last, and suffix.
    """
    user_obj = getattr(person, "user", None)
    return " ".join(
        [
            getattr(person, "prefix_name", "") or "",
            getattr(user_obj, "first_name", "") or "",
            getattr(person, "middle_name", "") or "",
            getattr(user_obj, "last_name", "") or "",
            getattr(person, "suffix_name", "") or "",
        ]
    ).strip()
