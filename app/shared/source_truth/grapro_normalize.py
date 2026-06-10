"""GradPro normalization helpers for source-truth imports."""

from __future__ import annotations

import re
from datetime import datetime
from typing import TypeAlias

from app.timetable.utils import normalize_academic_year, normalize_sem_code

TermPartsT: TypeAlias = tuple[str, str]

TERM_RX = re.compile(
    r"(?P<year>\d{4}[/-]\d{4}|\d{4}).*?(?P<sem>[123]|1st|2nd|3rd|summer|vac)", re.I
)
DATE_FORMATS = (
    "%m/%d/%y %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%y",
    "%m/%d/%Y",
    "%Y-%m-%d",
)


def gradpro_date_value(value: str) -> str:
    """Return an ISO date for common GradPro date strings."""
    text = (value or "").strip()
    if not text:
        return ""
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def gradpro_term_parts(value: str) -> TermPartsT:
    """Return ``(academic_year, semester_no)`` from a GradPro term label."""
    text = (value or "").strip()
    if not text:
        return "", ""
    match = TERM_RX.search(text)
    if match is None:
        return "", ""
    year = match.group("year").replace("-", "/")
    semester = _semester_number(match.group("sem"))
    return year, semester


def gradpro_semester_code(value: str) -> str:
    """Return a TUSIS semester code from a GradPro term label."""
    academic_year, semester = gradpro_term_parts(value)
    if not academic_year or not semester:
        return ""
    return normalize_sem_code("", year_value=academic_year, sem_value=semester)


def gradpro_normalized_term_key(value: str) -> str:
    """Return a compact term comparison key."""
    academic_year, semester = gradpro_term_parts(value)
    if not academic_year or not semester:
        return ""
    return f"{normalize_academic_year(academic_year)}|{semester}"


def _semester_number(value: str) -> str:
    """Collapse GradPro semester labels to numeric TUSIS terms."""
    token = (value or "").strip().lower()
    if token.startswith("2"):
        return "2"
    if token.startswith("3") or token in {"summer", "vac"}:
        return "3"
    return "1"


__all__ = [
    "gradpro_date_value",
    "gradpro_normalized_term_key",
    "gradpro_semester_code",
    "gradpro_term_parts",
]
