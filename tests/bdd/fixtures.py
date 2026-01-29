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
    student: object | None = None


@pytest.fixture
def student_context() -> StudentContext:
    """State container for BDD steps in this module."""
    return StudentContext()


@dataclass
class PortalContext:
    """Shared state for portal role BDD steps."""

    username: str | None = None
    is_student: bool = False


@pytest.fixture
def portal_context() -> PortalContext:
    """State container for portal role BDD steps."""
    return PortalContext()


@dataclass
class RegistrarContext:
    """Shared state for registrar dashboard BDD steps."""

    user: object | None = None
    semester: Semester | None = None
    student: object | None = None


@pytest.fixture
def registrar_context() -> RegistrarContext:
    """State container for registrar dashboard BDD steps."""
    return RegistrarContext()
