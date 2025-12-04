"""Functional helpers to assemble reusable CSV row pipelines."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from app.shared.utils import get_in_row

Row = dict[str, Any]
Transform = Callable[[Row], Row]


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
        value = (row.get(key) or "").strip()
        if not value:
            row[key] = default
        elif converter:
            row[key] = converter(value)
        else:
            row[key] = value
        return row

    return _apply


def setdefault_field(key: str, provider: Callable[[Row], str]) -> Transform:
    """Set a field using the provider when the current value is blank."""

    def _apply(row: Row) -> Row:
        if not get_in_row(key, row):
            row[key] = provider(row)
        return row

    return _apply


def extract_course_codes(row: Row) -> tuple[str, str]:
    """Return college/department codes derived from the row content."""
    from app.shared.utils import expand_course_code  # defer import to avoid cycles

    course_code = row.pop("course_code", "") or row.get("course_dept", "")
    course_no = get_in_row("course_no", row)
    merged = f"{course_code}{course_no}".strip()
    if not merged:
        return (
            get_in_row("college_code", row) or "",
            get_in_row("course_dept", row) or "",
        )

    try:
        college_code, dept_code, _ = expand_course_code(merged, row=row)
    except AssertionError:
        return (
            get_in_row("college_code", row) or "",
            get_in_row("course_dept", row) or "",
        )
    return college_code, dept_code


def set_course_codes(row: Row) -> Row:
    """Populate college_code/course_dept when absent by inspecting course columns."""
    college_code, dept_code = extract_course_codes(row)
    row.setdefault("college_code", college_code)
    row.setdefault("course_dept", dept_code)
    return row


def first_value(row: Row, keys: Sequence[str]) -> str:
    """Return the first non-empty value found in *keys*."""
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""
