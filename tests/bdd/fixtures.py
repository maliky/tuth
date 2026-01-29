"""Shared fixtures for pytest-bdd tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.timetable.models.semester import Semester


@dataclass
class StudentContext:
    """Shared state for student dashboard BDD steps."""

    user: object | None = None
    semester: Semester | None = None


@pytest.fixture
def student_context() -> StudentContext:
    """State container for BDD steps in this module."""
    return StudentContext()
