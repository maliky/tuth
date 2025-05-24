import pytest
from datetime import date
from django.core.exceptions import ValidationError
from app.timetable.models import AcademicYear, Semester, Term


@pytest.mark.django_db
def test_semester_identical_start_end():
    ay = AcademicYear.objects.create(start_date=date(2024, 8, 1))
    sem = Semester(
        academic_year=ay,
        number=1,
        start_date=date(2024, 8, 15),
        end_date=date(2024, 8, 15),
    )
    sem.clean()


@pytest.mark.django_db
def test_semester_overlap():
    ay = AcademicYear.objects.create(start_date=date(2024, 8, 1))
    Semester.objects.create(
        academic_year=ay,
        number=1,
        start_date=date(2024, 8, 1),
        end_date=date(2025, 1, 1),
    )
    sem = Semester(
        academic_year=ay,
        number=2,
        start_date=date(2024, 12, 15),
        end_date=date(2025, 4, 1),
    )
    with pytest.raises(ValidationError):
        sem.clean()


@pytest.mark.django_db
def test_semester_out_of_range():
    ay = AcademicYear.objects.create(start_date=date(2024, 8, 1))
    sem = Semester(
        academic_year=ay,
        number=1,
        start_date=date(2025, 8, 1),
        end_date=date(2025, 9, 1),
    )
    with pytest.raises(ValidationError):
        sem.clean()


@pytest.mark.django_db
def test_semester_gap_allowed():
    ay = AcademicYear.objects.create(start_date=date(2024, 8, 1))
    Semester.objects.create(
        academic_year=ay,
        number=1,
        start_date=date(2024, 8, 1),
        end_date=date(2024, 12, 31),
    )
    sem = Semester(
        academic_year=ay,
        number=2,
        start_date=date(2025, 1, 15),
        end_date=date(2025, 4, 30),
    )
    sem.clean()


@pytest.mark.django_db
def test_term_overlap():
    ay = AcademicYear.objects.create(start_date=date(2024, 8, 1))
    sem = Semester.objects.create(
        academic_year=ay,
        number=1,
        start_date=date(2024, 8, 1),
        end_date=date(2024, 12, 31),
    )
    Term.objects.create(
        semester=sem,
        number=1,
        start_date=date(2024, 8, 1),
        end_date=date(2024, 10, 1),
    )
    term = Term(
        semester=sem,
        number=2,
        start_date=date(2024, 9, 15),
        end_date=date(2024, 11, 1),
    )
    with pytest.raises(ValidationError):
        term.clean()


@pytest.mark.django_db
def test_term_out_of_range():
    ay = AcademicYear.objects.create(start_date=date(2024, 8, 1))
    sem = Semester.objects.create(
        academic_year=ay,
        number=1,
        start_date=date(2024, 8, 1),
        end_date=date(2024, 12, 31),
    )
    term = Term(
        semester=sem,
        number=1,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 10),
    )
    with pytest.raises(ValidationError):
        term.clean()


@pytest.mark.django_db
def test_term_gap_allowed():
    ay = AcademicYear.objects.create(start_date=date(2024, 8, 1))
    sem = Semester.objects.create(
        academic_year=ay,
        number=1,
        start_date=date(2024, 8, 1),
        end_date=date(2024, 12, 31),
    )
    Term.objects.create(
        semester=sem,
        number=1,
        start_date=date(2024, 8, 1),
        end_date=date(2024, 9, 1),
    )
    term = Term(
        semester=sem,
        number=2,
        start_date=date(2024, 9, 15),
        end_date=date(2024, 10, 1),
    )
    term.clean()


@pytest.mark.django_db
def test_term_identical_start_end():
    ay = AcademicYear.objects.create(start_date=date(2024, 8, 1))
    sem = Semester.objects.create(
        academic_year=ay,
        number=1,
        start_date=date(2024, 8, 1),
        end_date=date(2024, 12, 31),
    )
    term = Term(
        semester=sem,
        number=1,
        start_date=date(2024, 9, 1),
        end_date=date(2024, 9, 1),
    )
    term.clean()
