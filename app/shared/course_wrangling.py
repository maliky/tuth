"""Shared course-code parsing and matching helpers.

The rules here mirror the maintained TUCurricula tooling: revised course
codes are 3-5 department letters, three digits, and an optional letter suffix.
Legacy import rows can be repaired, but the repair reason remains explicit so
source-truth reports can audit it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypeAlias

from app.shared.utils import parse_str

CourseIdentityT: TypeAlias = tuple[str, str]
DeptAliasMapT: TypeAlias = dict[str, str]

CANONICAL_DEPT_RX = re.compile(r"^[A-Z]{3,5}$")
LEGACY_DEPT_RX = re.compile(r"^[A-Z]{2,5}$")
CANONICAL_NO_RX = re.compile(r"^\d{3}[A-Z]?$")
LEGACY_NO_RX = re.compile(r"^\d{1,2}[A-Z]?$")
STATUS_SUFFIX_RX = re.compile(r"\s*-(?:TODO|ORPH)\b.*$", re.I)
PAREN_SUFFIX_RX = re.compile(r"(?<=\d)\(([A-Z])\)", re.I)
TOKEN_RX = re.compile(r"[^A-Z0-9]+")

COURSE_PATTERN = re.compile(
    r"(?:(?P<college>[A-Z]{3,4})-)?"
    r"(?P<dept>[A-Z]{3,5})[\s_-]*"
    r"(?P<num>[0-9]{3}(?:[A-Z]|\([A-Z]\))?)(?![A-Z0-9])",
    re.I,
)
LEGACY_COURSE_PATTERN = re.compile(
    r"(?:(?P<college>[A-Z]{3,4})-)?"
    r"(?P<dept>[A-Z]{2,5})[\s_-]*"
    r"(?P<num>[0-9]{1,3}(?:[A-Z]|\([A-Z]\))?)(?![A-Z0-9])",
    re.I,
)

LEGACY_DEPT_ALIASES: DeptAliasMapT = {
    "AGR": "AGRI",
    "BIO": "BIOL",
    "BUS": "BUSA",
    "CHE": "CHEM",
    "CSE": "CSEN",
    "CSENG": "CSEN",
    "ECD": "ECED",
    "EDU": "EDUC",
    "EDUP": "PEDU",
    "EED": "EEDU",
    "GLE": "GLEB",
    "NUR": "NURS",
    "PEDU": "PHED",
    "PH": "PUBH",
}


@dataclass(frozen=True)
class CourseIdentityResultT:
    """Parsed course identity with provenance for audit reporting."""

    department: str
    number: str
    source: str
    repair_reason: str = ""


def normalize_token(value: str | None) -> str:
    """Return an uppercase alphanumeric token for deterministic comparison."""
    return TOKEN_RX.sub("", str(value or "").upper())


def course_key(dept: str | None, number: str | None) -> str:
    """Return the compact dept+number comparison key."""
    return normalize_token(f"{dept or ''}{number or ''}")


def compact_course_code(value: object) -> str:
    """Return an uppercase course-code token with transport whitespace removed."""
    text = strip_course_status_suffix(parse_str(value, "upper"))
    return re.sub(r"\s+", "", text)


def strip_course_status_suffix(value: str) -> str:
    """Remove TUCurricula audit suffixes such as ``-TODO`` and ``-ORPH``."""
    return STATUS_SUFFIX_RX.sub("", value.strip())


def normalize_course_number(value: str | None) -> str:
    """Normalize legacy course numbers like ``101.0`` into import-safe text."""
    text = compact_course_code(value)
    if text.endswith(".0"):
        text = text[:-2]
    return PAREN_SUFFIX_RX.sub(r"\1", text)


def split_course_code(value: str | None) -> CourseIdentityT:
    """Split a visible course code into department and number."""
    parsed = parse_course_code_result(value)
    if parsed is None:
        return "", ""
    return parsed.department, parsed.number


def parse_course_code_result(
    value: object, source: str = "course_code"
) -> CourseIdentityResultT | None:
    """Parse one visible or compact course code."""
    text = strip_course_status_suffix(parse_str(value, "upper"))
    if not text:
        return None
    canonical = COURSE_PATTERN.search(text)
    if canonical is not None:
        return CourseIdentityResultT(
            canonical.group("dept").upper(),
            normalize_course_number(canonical.group("num")),
            source,
            _dept_repair_reason(canonical.group("dept").upper()),
        )
    legacy = LEGACY_COURSE_PATTERN.search(text)
    if legacy is None:
        return None
    dept = legacy.group("dept").upper()
    raw_number = normalize_course_number(legacy.group("num"))
    number = _pad_course_number(raw_number)
    number_reason = "legacy_padded_number" if number != raw_number else ""
    reason = _join_repair_reasons(number_reason, _dept_repair_reason(dept))
    return CourseIdentityResultT(dept, number, source, reason)


def parse_course_identity_result(
    dept_raw: str | None, no_raw: str | None
) -> CourseIdentityResultT | None:
    """Parse messy legacy department/number cells into a clean course identity."""
    dept = compact_course_code(dept_raw)
    number = normalize_course_number(no_raw)
    direct = _direct_identity(dept, number)
    if direct is not None:
        return direct

    for source, candidate in (
        ("dept_as_course_code", dept_raw),
        ("number_as_course_code", no_raw),
        ("combined_fields", f"{dept}{number}" if dept or number else ""),
    ):
        parsed = parse_course_code_result(candidate, source=source)
        if parsed is not None:
            return parsed
    return None


def parse_course_identity(
    dept_raw: str | None, no_raw: str | None
) -> CourseIdentityT | None:
    """Return a normalized ``(department, course_no)`` pair when parseable."""
    parsed = parse_course_identity_result(dept_raw, no_raw)
    if parsed is None:
        return None
    return parsed.department, parsed.number


def invalid_course_identity_reason(dept_raw: str | None, no_raw: str | None) -> str:
    """Return a compact reason for rejecting a legacy course identity."""
    dept = compact_course_code(dept_raw)
    number = normalize_course_number(no_raw)
    if not dept and not number:
        return "missing_course_identity"
    if not number:
        return "missing_course_number"
    if not any(ch.isdigit() for ch in number):
        return "course_number_has_no_digit"
    if not LEGACY_DEPT_RX.match(dept):
        return "invalid_department_code"
    return "invalid_course_identity"


def _direct_identity(dept: str, number: str) -> CourseIdentityResultT | None:
    """Return a direct identity result when separated cells are parseable."""
    if not LEGACY_DEPT_RX.match(dept):
        return None
    dept_reason = _dept_repair_reason(dept)
    if CANONICAL_NO_RX.match(number):
        source = "direct_canonical" if not dept_reason else "direct_legacy_department"
        return CourseIdentityResultT(dept, number, source, dept_reason)
    if LEGACY_NO_RX.match(number):
        reason = _join_repair_reasons("legacy_padded_number", dept_reason)
        return CourseIdentityResultT(
            dept, _pad_course_number(number), "direct_legacy_number", reason
        )
    return None


def _dept_repair_reason(dept: str) -> str:
    """Return a repair note for non-canonical but preserved departments."""
    if CANONICAL_DEPT_RX.match(dept):
        return ""
    if dept in LEGACY_DEPT_ALIASES:
        return "legacy_department_alias_candidate"
    if LEGACY_DEPT_RX.match(dept):
        return "legacy_department_shape"
    return "invalid_department_code"


def _pad_course_number(number: str) -> str:
    """Pad the numeric part of a legacy course number to three digits."""
    match = re.match(r"^(\d{1,2})([A-Z]?)$", number)
    if not match:
        return number
    return f"{int(match.group(1)):03d}{match.group(2)}"


def _join_repair_reasons(*reasons: str) -> str:
    """Join non-empty repair reasons in deterministic report form."""
    return ";".join(reason for reason in reasons if reason)


__all__ = [
    "CourseIdentityResultT",
    "CourseIdentityT",
    "COURSE_PATTERN",
    "LEGACY_DEPT_ALIASES",
    "compact_course_code",
    "course_key",
    "invalid_course_identity_reason",
    "normalize_course_number",
    "normalize_token",
    "parse_course_code_result",
    "parse_course_identity",
    "parse_course_identity_result",
    "split_course_code",
]
