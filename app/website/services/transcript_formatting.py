"""Formatting helpers for transcript document values."""

from __future__ import annotations

from datetime import date


def fmt_number(value: float | int) -> str:
    """Return transcript numeric values rounded to whole units."""
    return str(round(float(value)))


def fmt_gpa(points: float, credits: int) -> str:
    """Return a GPA value or N/A when there are no GPA credits."""
    if not credits:
        return "N/A"
    return f"{points / credits:.2f}"


def fmt_date(value: date | None, *, short: bool = False) -> str:
    """Return a compact transcript date label."""
    if value is None:
        return ""
    if short:
        return value.strftime("%d/%m/%y")
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def fmt_abbrev_date(value: date | None) -> str:
    """Return a readable abbreviated month transcript date label."""
    if value is None:
        return ""
    return f"{value.strftime('%b')} {value.day}, {value.year}"


__all__ = ["fmt_abbrev_date", "fmt_date", "fmt_gpa", "fmt_number"]
