"""Test timetable dates module."""

from datetime import date

import pytest
from django.core.exceptions import ValidationError

from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester
from app.timetable.models.term import Term


def make_semester(
    ay_start: date,
    sem_start: date,
    sem_end: date,
    sem_number: int = 1,
    *,
    year: AcademicYear | None = None,
) -> tuple[AcademicYear, Semester]:
    """Return (year, semester) helper."""

    ay = year or AcademicYear.objects.create(start_date=ay_start)
    sem = Semester.objects.create(
        academic_year=ay, number=sem_number, start_date=sem_start, end_date=sem_end
    )
    return ay, sem


def make_term(
    sem: Semester, start: date, end: date, number: int = 1, *, persist: bool = False
) -> Term:
    """Return a term instance bound to sem."""

    term = Term(semester=sem, number=number, start_date=start, end_date=end)
    if persist:
        term.save()
    return term


@pytest.mark.django_db
def test_semester_identical_start_end():
    # may need to be replaced with fixtures
    ay, sem = make_semester(date(2024, 8, 1), date(2024, 8, 15), date(2024, 8, 15))
    sem.clean()


@pytest.mark.django_db
def test_semester_overlap():
    ay, _ = make_semester(date(2024, 8, 1), date(2024, 8, 1), date(2025, 1, 1))
    _, sem = make_semester(
        date(2024, 8, 1), date(2024, 12, 15), date(2025, 4, 1), sem_number=2, year=ay
    )
    with pytest.raises(ValidationError):
        sem.clean()


@pytest.mark.django_db
def test_semester_out_of_range():
    ay, sem = make_semester(date(2024, 8, 1), date(2025, 8, 1), date(2025, 9, 1))
    with pytest.raises(ValidationError):
        sem.clean()


@pytest.mark.django_db
def test_semester_gap_allowed():
    ay, _ = make_semester(date(2024, 8, 1), date(2024, 8, 1), date(2024, 12, 31))
    _, sem = make_semester(
        date(2024, 8, 1), date(2025, 1, 15), date(2025, 4, 30), sem_number=2, year=ay
    )
    sem.clean()


@pytest.mark.django_db
def test_term_overlap():
    ay, sem = make_semester(date(2024, 8, 1), date(2024, 8, 1), date(2024, 12, 31))
    make_term(sem, date(2024, 8, 1), date(2024, 10, 1), persist=True)
    term = make_term(sem, date(2024, 9, 15), date(2024, 11, 1), number=2)
    with pytest.raises(ValidationError):
        term.clean()


@pytest.mark.django_db
def test_term_out_of_range():
    ay, sem = make_semester(date(2024, 8, 1), date(2024, 8, 1), date(2024, 12, 31))
    term = make_term(sem, date(2025, 1, 1), date(2025, 1, 10))
    with pytest.raises(ValidationError):
        term.clean()


@pytest.mark.django_db
def test_term_gap_allowed():
    ay, sem = make_semester(date(2024, 8, 1), date(2024, 8, 1), date(2024, 12, 31))
    make_term(sem, date(2024, 8, 1), date(2024, 9, 1), persist=True)
    term = make_term(sem, date(2024, 9, 15), date(2024, 10, 1), number=2)
    term.clean()


@pytest.mark.django_db
def test_term_identical_start_end():
    ay, sem = make_semester(date(2024, 8, 1), date(2024, 8, 1), date(2024, 12, 31))
    term = make_term(sem, date(2024, 9, 1), date(2024, 9, 1))
    term.clean()
