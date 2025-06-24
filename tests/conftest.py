"""Reusable fixtures.

pytest auto-discover it.
"""

from __future__ import annotations

pytest_plugins = [
    "tests.timetable.fixture",
    "tests.academics.fixture",
    "tests.people.fixture",
    "tests.spaces.fixture",
]
