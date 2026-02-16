"""Shared fixtures for pytest-bdd tests."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

import pytest

from app.people.models.student import Student
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester


class PortalUserT(Protocol):
    """Minimal user interface needed by portal-related tests."""

    username: str


@dataclass
class StdContext:
    """Shared state for student dashboard BDD steps."""

    user: PortalUserT | None = None
    semester: Semester | None = None
    student: Student | None = None
    section: Section | None = None
    fee_due: Decimal | None = None


@pytest.fixture
def std_context() -> StdContext:
    """State container for BDD steps in this module."""
    return StdContext()


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
class RegContext:
    """Shared state for registrar dashboard BDD steps."""

    user: PortalUserT | None = None
    semester: Semester | None = None
    student: Student | None = None


@pytest.fixture
def reg_context() -> RegContext:
    """State container for registrar dashboard BDD steps."""
    return RegContext()
