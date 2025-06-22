"""Reusable fixtures.

pytest auto-discover it.
"""

from __future__ import annotations

pytest_plugins = [
    "tests.fixtures.timetable",
    "tests.fixtures.academics",
    "tests.fixtures.people",
    "tests.fixtures.spaces",
]
