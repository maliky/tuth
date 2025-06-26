"""Test fixture for academics."""

from __future__ import annotations

from typing import Callable, TypeAlias

from app.academics.models.curriculum import Curriculum
from app.academics.models.program import Program
import pytest

from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.department import Department

CollegeFactory: TypeAlias = Callable[[str], College]
CourseFactory: TypeAlias = Callable[[str, str], Course]
DepartmentFactory: TypeAlias = Callable[[str], Department]


@pytest.fixture
def college() -> College:
    return College.get_default()


@pytest.fixture
def college_factory() -> CollegeFactory:
    def _make(code: str = "COAS") -> College:
        """Create College with matching code."""
        return College.objects.create(code=code)

    return _make


@pytest.fixture
def course() -> Course:
    return Course.objects.create(
        number="101",
        title="Course de test",
    )


@pytest.fixture
def course_factory() -> CourseFactory:
    def _make(number: str = "101", title: str = "Course") -> Course:
        return Course.objects.create(number=number, title=title)

    return _make


@pytest.fixture
def curriculum(course_factory: CourseFactory) -> Curriculum:
    cur = Curriculum.get_default()
    course1 = course_factory("101", "The first course.")
    course2 = course_factory("102", "The second course.")
    Program.objects.bulk_create(
        [
            Program(curriculum=cur, course=course1),
            Program(curriculum=cur, course=course2),
        ]
    )
    return cur


@pytest.fixture
def curriculum_empty() -> Curriculum:
    cur = Curriculum.objects.create(
        short_name="EMPTY_CUR", long_name="An Empty Curriculum (no courses)"
    )
    return cur


@pytest.fixture
def department() -> Department:
    return Department.get_default()


@pytest.fixture
def department_factory() -> DepartmentFactory:
    def _make(code: str = "GEN") -> Department:
        return Department.get_default(code)

    return _make


@pytest.fixture
def program(curriculum_empty: Curriculum, course: Course) -> Program:
    return Program.objects.create(
        curriculum=curriculum_empty,
        course=course,
    )
