"""Functional helpers to assemble reusable CSV row pipelines."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from app.shared.course_wrangling import (
    CourseIdentityResultT,
    CourseIdentityT,
    compact_course_code,
    invalid_course_identity_reason,
    normalize_course_number,
    parse_course_identity,
    parse_course_identity_result,
)
from app.shared.types import Row, Transform
from app.shared.utils import get_in_row, parse_str

# stuff here should go to academics.utils

CourseDeptKeysT = tuple[str, ...]
COURSE_DEPT_KEYS: CourseDeptKeysT = ("dept_code", "course_dept", "course_name")
COURSE_NO_KEYS: CourseDeptKeysT = ("course_no",)

__all__ = [
    "CourseIdentityResultT",
    "CourseIdentityT",
    "compact_course_code",
    "invalid_course_identity_reason",
    "normalize_course_number",
    "parse_course_identity",
    "parse_course_identity_result",
]


def pipeline(row: Row, *transforms: Transform) -> Row:
    """Apply a sequence of transforms to the row, returning the mutated dict."""
    for transform in transforms:
        row = transform(row)
    return row


def rename_headers(mapping: Mapping[str, str]) -> Transform:
    """Return a transform that maps legacy headers into the canonical schema."""

    def _apply(row: Row) -> Row:
        for legacy, modern in mapping.items():
            if modern in row:
                continue
            value = row.get(legacy)
            if value is not None:
                row[modern] = value
        return row

    return _apply


def normalize_field(key: str, normalizer: Callable[[str | None], str]) -> Transform:
    """Return a transform that normalizes a field using the provided callable."""

    def _apply(row: Row) -> Row:
        row[key] = normalizer(row.get(key))
        return row

    return _apply


def coerce_field(
    key: str,
    *,
    default: str = "",
    converter: Callable[[str], str] | None = None,
) -> Transform:
    """Coerce a textual field into a canonical representation with a default."""

    def _apply(row: Row) -> Row:
        value = parse_str(row.get(key))
        if not value:
            row[key] = default
        elif converter:
            row[key] = converter(value)
        else:
            row[key] = value
        return row

    return _apply


def setdft_field(key: str, provider: Callable[[Row], str]) -> Transform:
    """Set a field using the provider when the current value is blank."""

    def _apply(row: Row) -> Row:
        if not get_in_row(key, row):
            row[key] = provider(row)
        return row

    return _apply


def first_value(row: Mapping[str, Any] | None, keys: Sequence[str]) -> str:
    """Return the first non-empty value found in *keys*."""
    if row is None:
        return ""
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def get_course_dept(row: Mapping[str, Any] | None) -> str:
    """Return the canonical course department value from accepted row aliases."""
    return first_value(row, COURSE_DEPT_KEYS)


def require_course_identity(row: Mapping[str, Any] | None) -> tuple[str, str]:
    """Return ``(dept_code, course_no)`` or fail with a normalized error."""
    dept_code = get_course_dept(row)
    course_no = first_value(row, COURSE_NO_KEYS)
    identity = parse_course_identity(dept_code, course_no)
    if identity is None:
        raise ValueError(
            "A parseable course_no and one of dept_code/course_dept/course_name "
            f"are required in row {row} context."
        )
    return identity


def set_crs_codes(row: Row) -> Row:
    """Populate college_code/course_dept when absent by inspecting course columns."""
    college_code, dept_code = extract_crs_codes(row)
    if not get_in_row("college_code", row):
        row["college_code"] = college_code
    if not get_in_row("course_dept", row):
        row["course_dept"] = dept_code
    if not get_in_row("dept_code", row):
        row["dept_code"] = dept_code
    return row


def extract_crs_codes(row: Row) -> tuple[str, str]:
    """Return college/department codes derived from the row content.

    Assumptions are that course_code is the small MATH101,
    MATH is dept_code and 101 is course_no.
    renaming should have been done before reaching here.
    We assure columns to be present in row.
    """
    from app.academics.utils import expand_crs_code  # defer import to avoid cycles

    # > Check the stuff here
    # could also be dept_code no ?
    course_code = get_in_row("course_code", row)

    if course_code:
        try:
            college_code, dept_code, _ = expand_crs_code(course_code, row=row)
            return college_code, dept_code
        except AssertionError:
            pass

    identity = parse_course_identity(get_course_dept(row), get_in_row("course_no", row))
    if identity is not None:
        return get_in_row("college_code", row), identity[0]

    course_code = course_code or f"{get_course_dept(row)}{get_in_row('course_no', row)}"
    return (get_in_row("college_code", row), course_code)
