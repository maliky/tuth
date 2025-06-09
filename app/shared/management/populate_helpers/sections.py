"""Helpers to import section data from CSV.

This module provides :func:`populate_sections_from_csv` which creates the
fundamental timetable objects (academic years, semesters, courses, instructors,
sessions and sections) from a CSV stream.  It is designed for seeding an empty
database using the exported ``cleaned_tscc.csv`` file.
"""

from __future__ import annotations


def parse_int(value: str | None) -> int | None:
    """Return ``int(value)`` when possible.

    Handles numbers represented as ``"1.0"`` or ``"1"`` and ignores
    non-numeric strings by returning ``None``.
    """

    if value is None:
        return None

    token = str(value).strip()
    try:
        return int(float(token))
    except ValueError:
        return None
