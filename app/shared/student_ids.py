"""Student identifier normalization helpers."""

from __future__ import annotations

import re
from typing import TypeAlias

StudentIdKeyT: TypeAlias = str

TU_NUMERIC_STUDENT_ID_RE = re.compile(r"^tu\s*-?\s*0*(?P<number>\d+)$", re.I)
DIGIT_RE = re.compile(r"\d+")


def canonical_student_id(value: str) -> str:
    """Return a canonical student id while preserving non-TU legacy ids."""
    clean_value = value.strip()
    match = TU_NUMERIC_STUDENT_ID_RE.match(clean_value)
    if match is None:
        return clean_value
    return f"TU-{int(match.group('number')):05d}"


def student_id_exact_key(value: str) -> StudentIdKeyT:
    """Return the key used to detect exact/case student-id duplicates."""
    return canonical_student_id(value).casefold()


def student_id_digit_key(value: str) -> StudentIdKeyT:
    """Return a numeric overlap key for manual duplicate review."""
    digits = "".join(DIGIT_RE.findall(value))
    if not digits:
        return ""
    return str(int(digits))


__all__ = [
    "canonical_student_id",
    "student_id_digit_key",
    "student_id_exact_key",
]
