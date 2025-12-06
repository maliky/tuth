"""Shared utilities for building cached name-based import helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Hashable, TypeVar

from app.people.utils import mk_password, mk_username, split_name


@dataclass
class NameParts:
    """Parsed representation of a raw name suitable for user defaults."""

    prefix: str
    first: str
    middle: str
    last: str
    suffix: str

    def capitalized_defaults(self) -> dict[str, str]:
        """Return admin-friendly defaults derived from the parsed name."""
        return {
            "first_name": self.first.capitalize(),
            "last_name": self.last.capitalize(),
            "name_prefix": self.prefix,
            "middle_name": self.middle,
            "name_suffix": self.suffix,
        }


def parse_name(raw: str | None, *, fallback_first: str = "", fallback_last: str = "") -> NameParts:
    """Split a name and fill sensible defaults for missing parts."""
    prefix, first, middle, last, suffix = split_name(raw or "")
    first = first or fallback_first or "Default"
    last = last or fallback_last or "User"
    return NameParts(prefix=prefix, first=first, middle=middle, last=last, suffix=suffix)


def build_username(
    first: str,
    last: str,
    *,
    middle: str = "",
    prefix_len: int | None = None,
    unique: bool = False,
    exclude: set[str] | None = None,
) -> str:
    """Standardised interface around mk_username."""
    return mk_username(
        first,
        last,
        middle=middle,
        unique=unique,
        exclude=exclude,
        prefix_len=prefix_len,
    )


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
