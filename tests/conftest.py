"""Project-level pytest configuration."""

from __future__ import annotations

from typing import Generator

import pytest

from app.academics import ensures as academics_ensures
from app.people import ensure_people as people_ensures
from app.timetable import ensures as timetable_ensures

# Expose shared fixture modules for all tests.
pytest_plugins = [
    "tests.academics.fixture",
    "tests.bdd.fixtures",
    "tests.selenium.fixtures_browser",
    "tests.selenium.fixtures_portal",
    "tests.selenium.fixtures_registrar_grades",
    "tests.selenium.fixtures_registrar",
    "tests.selenium.fixtures_finance",
    "tests.people.fixture",
    "tests.registry.fixture",
    "tests.shared.fixture",
    "tests.shared.permissions_fixtures",
    "tests.spaces.fixture",
    "tests.timetable.fixture",
]


def _clear_maps(*maps) -> None:
    for mapping in maps:
        mapping.clear()


@pytest.fixture(autouse=True)
def _clear_ensure_caches() -> Generator[None, None, None]:
    _clear_maps(
        academics_ensures.COLLEGE_CACHE,
        academics_ensures.DEPARTMENT_CACHE,
        academics_ensures.COURSE_CACHE,
        academics_ensures.CURRICULUM_CACHE,
        academics_ensures.CURRICULUM_COURSE_CACHE,
        academics_ensures.CREDIT_HOUR_CACHE,
        academics_ensures.COLLEGE_ID_CACHE,
        academics_ensures.COLLEGE_BY_ID_CACHE,
        academics_ensures.DEPARTMENT_ID_CACHE,
        academics_ensures.DEPARTMENT_BY_ID_CACHE,
        academics_ensures.COURSE_ID_CACHE,
        academics_ensures.COURSE_BY_ID_CACHE,
        academics_ensures.CURRICULUM_ID_CACHE,
        academics_ensures.CURRICULUM_BY_ID_CACHE,
        academics_ensures.CURRICULUM_COURSE_ID_CACHE,
        timetable_ensures.SEMESTER_CACHE,
        timetable_ensures.SECTION_CACHE,
        timetable_ensures.SEMESTER_ID_CACHE,
        timetable_ensures.SECTION_ID_CACHE,
        timetable_ensures.SCHEDULE_ID_CACHE,
        timetable_ensures.ROOM_ID_CACHE,
        timetable_ensures.SESSION_ID_CACHE,
        people_ensures.FACULTY_CACHE,
        people_ensures.STUDENT_ID_CACHE,
    )
    yield
    _clear_maps(
        academics_ensures.COLLEGE_CACHE,
        academics_ensures.DEPARTMENT_CACHE,
        academics_ensures.COURSE_CACHE,
        academics_ensures.CURRICULUM_CACHE,
        academics_ensures.CURRICULUM_COURSE_CACHE,
        academics_ensures.CREDIT_HOUR_CACHE,
        academics_ensures.COLLEGE_ID_CACHE,
        academics_ensures.COLLEGE_BY_ID_CACHE,
        academics_ensures.DEPARTMENT_ID_CACHE,
        academics_ensures.DEPARTMENT_BY_ID_CACHE,
        academics_ensures.COURSE_ID_CACHE,
        academics_ensures.COURSE_BY_ID_CACHE,
        academics_ensures.CURRICULUM_ID_CACHE,
        academics_ensures.CURRICULUM_BY_ID_CACHE,
        academics_ensures.CURRICULUM_COURSE_ID_CACHE,
        timetable_ensures.SEMESTER_CACHE,
        timetable_ensures.SECTION_CACHE,
        timetable_ensures.SEMESTER_ID_CACHE,
        timetable_ensures.SECTION_ID_CACHE,
        timetable_ensures.SCHEDULE_ID_CACHE,
        timetable_ensures.ROOM_ID_CACHE,
        timetable_ensures.SESSION_ID_CACHE,
        people_ensures.FACULTY_CACHE,
        people_ensures.STUDENT_ID_CACHE,
    )


@pytest.fixture(autouse=True)
def _strict_stdcurrienroll(settings) -> None:
    """Fail fast in tests when legacy curriculum FK fallback is used."""
    settings.STRICT_STDCURRIENROLL = True
