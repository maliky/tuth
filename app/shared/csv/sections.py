"""Helpers to import section data from CSV.

This module provides :func:populate_sections_from_csv which creates the
fundamental timetable objects (academic years, semesters, courses, instructors,
sessions and sections) from a CSV stream.  It is designed for seeding an empty
database using the exported cleaned_tscc.csv file.
"""

from __future__ import annotations


def parse_int(value: str | None) -> int | None:
    """Safely convert a string to int.

    Parameters
    ----------
    value : str | None
        Raw numeric value possibly containing trailing decimals.

    Returns
    -------
    int | None
        The integer representation or None if conversion fails.
    """
    if value is None:
        return None

    token = str(value).strip()
    try:
        return int(float(token))
    except ValueError:
        return None
