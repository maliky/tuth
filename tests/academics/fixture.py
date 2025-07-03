"""Test fixture for academics."""

from __future__ import annotations

from typing import Callable, TypeAlias

import pytest

from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.academics.models.program import Program

CollegeFactory: TypeAlias = Callable[[str], College]
CourseFactory: TypeAlias = Callable[[str], Course]
CurriculumFactory: TypeAlias = Callable[[str], Curriculum]
DepartmentFactory: TypeAlias = Callable[[str], Department]
ProgramFactory: TypeAlias = Callable[[str, str], Program]


@pytest.fixture
def college() -> College:
    return College.get_default()


@pytest.fixture
def course() -> Course:
    return Course.get_default("111")


@pytest.fixture
def curriculum() -> Curriculum:
    return Curriculum.get_default()


@pytest.fixture
def department() -> Department:
    return Department.get_default("TSTD")


@pytest.fixture
def program() -> Program:
    return Program.get_default()


# ~~~~~~~~~~~~~~~~ DB Constraints  ~~~~~~~~~~~~~~~~


@pytest.fixture
def college_factory() -> CollegeFactory:
    def _make(code: str = "TEST") -> College:
        """Create College with matching code."""
        return College.objects.create(code=code)

    return _make


@pytest.fixture
def department_factory() -> DepartmentFactory:
    def _make(short_name: str = "DEPT_TEST") -> Department:
        return Department.get_default(short_name)

    return _make


@pytest.fixture
def curriculum_factory() -> CurriculumFactory:
    def _make(short_name: str = "CURRI_TEST") -> Curriculum:
        return Curriculum.get_default(short_name)

    return _make


@pytest.fixture
def course_factory() -> CourseFactory:
    def _make(number: str = "101") -> Course:
        return Course.get_default(number)

    return _make


@pytest.fixture
def program_factory(course_factory, curriculum_factory) -> ProgramFactory:
    def _make(course_num="111", curriculum_short_name: str = "CURRI_TEST") -> Program:
        course = course_factory(course_num)
        curriculum = curriculum_factory(curriculum_short_name)
        return Program(course=course, curriculum=curriculum)

    return _make
