"""Tests for student import resource normalization."""

from __future__ import annotations

from datetime import date

from app.people.admin.resources import StdResource


def test_student_resource_birth_date_accepts_iso_date() -> None:
    """Student import should accept SmartSchool ISO date-only values."""
    widget = StdResource().fields["birth_date"].widget

    assert widget.clean("1900-01-01") == date(1900, 1, 1)
    assert widget.clean("") is None
