"""College-code helpers for source-truth import bundles."""

from __future__ import annotations

from typing import TypeAlias

from app.academics.choices import COLLEGE_CODE
from app.shared.source_truth.io import RowT

CollegeFieldNamesT: TypeAlias = frozenset[str]

COLLEGE_FIELD_NAMES: CollegeFieldNamesT = frozenset(
    {
        "College",
        "college",
        "college_code",
        "curriculum_college_code",
        "course_college_code",
        "required_course_college_code",
    }
)


def canonical_college_code(value: object) -> str:
    """Return the canonical TU college code while preserving blanks/unknowns."""
    raw = "" if value is None else str(value).strip()
    if not raw:
        return ""
    return COLLEGE_CODE.get(raw.lower(), raw.upper())


def canonicalize_college_fields(row: RowT) -> RowT:
    """Return a row copy with known college-code fields canonicalized."""
    return {
        key: canonical_college_code(value) if key in COLLEGE_FIELD_NAMES else value
        for key, value in row.items()
    }


__all__ = ["canonical_college_code", "canonicalize_college_fields"]
