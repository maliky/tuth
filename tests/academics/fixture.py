"""Test fixture for academics."""

from __future__ import annotations

from typing import Callable, TypeAlias, cast

import pytest

from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.concentration import Major, Minor
from app.finance.models.invoice import CrsInvoice
from app.people.models.student import Student
from app.registry.models.credit_hours import CreditHour
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester
from tests.constants import D10

CollegeFactoryT: TypeAlias = Callable[[str], College]
CrsFactoryT: TypeAlias = Callable[[str], Course]
CurriFactoryT: TypeAlias = Callable[[str], Curriculum]
DepartmentFactoryT: TypeAlias = Callable[[str], Department]
CurriCrsFactoryT: TypeAlias = Callable[[str, str], CurriCrs]
CreditHourFactoryT: TypeAlias = Callable[[int], CreditHour]

InvoiceFactoryT: TypeAlias = Callable[[CurriCrs], CrsInvoice]


@pytest.fixture
def college() -> College:
    return College.get_dft()


@pytest.fixture
def course() -> Course:
    return Course.get_dft("111")


@pytest.fixture
def curriculum() -> Curriculum:
    return Curriculum.get_dft()


@pytest.fixture
def department() -> Department:
    return Department.get_dft("TSTD")


@pytest.fixture
def curriculum_course() -> CurriCrs:
    return CurriCrs.get_dft()


# ~~~~~~~~~~~~~~~~ DB Constraints  ~~~~~~~~~~~~~~~~


@pytest.fixture
def college_factory() -> CollegeFactoryT:
    def _make(code: str = "TEST") -> College:
        """Create College with matching code."""
        return College.objects.create(code=code)

    return _make


@pytest.fixture
def dpt_factory() -> DepartmentFactoryT:
    def _make(shortname: str = "DEPT_TEST") -> Department:
        return Department.get_dft(shortname)

    return _make


@pytest.fixture
def curri_factory() -> CurriFactoryT:
    def _make(short_name: str = "CURRI_TEST") -> Curriculum:
        return Curriculum.get_dft(short_name)

    return _make


@pytest.fixture
def crs_factory() -> CrsFactoryT:
    def _make(number: str = "101") -> Course:
        course = Course.get_dft(number)
        return course

    return _make


@pytest.fixture
def curriculum_course_factory(crs_factory, curri_factory) -> CurriCrsFactoryT:
    def _make(course_num="111", curriculum_short_name: str = "CURRI_TEST") -> CurriCrs:
        course = crs_factory(course_num)
        curriculum = curri_factory(curriculum_short_name)
        curriculum_course, _ = CurriCrs.objects.get_or_create(
            course=course, curriculum=curriculum
        )
        return curriculum_course

    return _make


@pytest.fixture
def major() -> Major:
    """Default major with one curriculum_course."""
    return Major.get_dft()


@pytest.fixture
def minor() -> Minor:
    """Default minor with one curriculum_course."""
    return Minor.get_dft()


@pytest.fixture
def dft_academic_year() -> AcademicYear:
    """Return the current academic year."""
    return AcademicYear.get_dft()


@pytest.fixture
def dft_sem() -> Semester:
    """Return the current semester."""
    return Semester.get_dft()


@pytest.fixture
def credit_hour() -> CreditHour:
    """Return the default credit hour."""
    return CreditHour.get_dft()


@pytest.fixture
def credit_hour_factory() -> CreditHourFactoryT:
    """Return a callable to create credit hour rows."""

    def _make(code: int = 3) -> CreditHour:
        return cast(CreditHour, CreditHour.objects.get(code=code))

    return _make


@pytest.fixture
def invoice_factory(dft_sem: Semester) -> InvoiceFactoryT:
    """Return a callable to create invoices for curriculum courses."""

    def _make(curriculum_course: CurriCrs) -> CrsInvoice:
        student = Student.get_dft()
        amount = D10
        return CrsInvoice.objects.create(
            curriculum_course=curriculum_course,
            student=student,
            semester=dft_sem,
            initial_amount_due=amount,
            balance=amount,
        )

    return _make
