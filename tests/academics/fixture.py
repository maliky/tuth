"""Test fixture for academics."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, TypeAlias, cast

import pytest

from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.academics.models.curriculum_course import CurriculumCourse
from app.academics.models.concentration import Major, Minor
from app.finance.models.invoice import Invoice
from app.people.models.student import Student
from app.registry.models.credit_hours import CreditHour
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester

CollegeFactoryT: TypeAlias = Callable[[str], College]
CourseFactoryT: TypeAlias = Callable[[str], Course]
CurriculumFactoryT: TypeAlias = Callable[[str], Curriculum]
DepartmentFactoryT: TypeAlias = Callable[[str], Department]
CurriculumCourseFactoryT: TypeAlias = Callable[[str, str], CurriculumCourse]
CreditHourFactoryT: TypeAlias = Callable[[int], CreditHour]
InvoiceFactoryT: TypeAlias = Callable[[CurriculumCourse], Invoice]


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
def curriculum_course() -> CurriculumCourse:
    return CurriculumCourse.get_default()


# ~~~~~~~~~~~~~~~~ DB Constraints  ~~~~~~~~~~~~~~~~


@pytest.fixture
def college_factory() -> CollegeFactoryT:
    def _make(code: str = "TEST") -> College:
        """Create College with matching code."""
        return College.objects.create(code=code)

    return _make


@pytest.fixture
def department_factory() -> DepartmentFactoryT:
    def _make(shortname: str = "DEPT_TEST") -> Department:
        return Department.get_default(shortname)

    return _make


@pytest.fixture
def curriculum_factory() -> CurriculumFactoryT:
    def _make(short_name: str = "CURRI_TEST") -> Curriculum:
        return Curriculum.get_default(short_name)

    return _make


@pytest.fixture
def course_factory() -> CourseFactoryT:
    def _make(number: str = "101") -> Course:
        course = Course.get_default(number)
        return course

    return _make


@pytest.fixture
def curriculum_course_factory(
    course_factory, curriculum_factory
) -> CurriculumCourseFactoryT:
    def _make(
        course_num="111", curriculum_short_name: str = "CURRI_TEST"
    ) -> CurriculumCourse:
        course = course_factory(course_num)
        curriculum = curriculum_factory(curriculum_short_name)
        curriculum_course, _ = CurriculumCourse.objects.get_or_create(
            course=course, curriculum=curriculum
        )
        return curriculum_course

    return _make


@pytest.fixture
def major() -> Major:
    """Default major with one curriculum_course."""
    return Major.get_default()


@pytest.fixture
def minor() -> Minor:
    """Default minor with one curriculum_course."""
    return Minor.get_default()


@pytest.fixture
def default_academic_year() -> AcademicYear:
    """Return the current academic year."""
    return AcademicYear.get_default()


@pytest.fixture
def default_semester() -> Semester:
    """Return the current semester."""
    return Semester.get_default()


@pytest.fixture
def credit_hour() -> CreditHour:
    """Return the default credit hour."""
    return CreditHour.get_default()


@pytest.fixture
def credit_hour_factory() -> CreditHourFactoryT:
    """Return a callable to create credit hour rows."""

    def _make(code: int = 3) -> CreditHour:
        return cast(CreditHour, CreditHour.objects.get(code=code))

    return _make


@pytest.fixture
def invoice_factory(default_semester: Semester) -> InvoiceFactoryT:
    """Return a callable to create invoices for curriculum courses."""

    def _make(curriculum_course: CurriculumCourse) -> Invoice:
        student = Student.get_default()
        return Invoice.objects.create(
            curriculum_course=curriculum_course,
            student=student,
            semester=default_semester,
            balance=Decimal("10.00"),
        )

    return _make
