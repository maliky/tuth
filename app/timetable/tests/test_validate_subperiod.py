"""Test the subperiod integrity."""

import pytest
from datetime import date
from django.core.exceptions import ValidationError

from app.timetable.utils import validate_subperiod
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester
from app.timetable.models.term import Term


@pytest.mark.django_db
def test_valid_subperiod_inside_container():
    ay = AcademicYear.objects.create(start_date=date(2025, 9, 1))
    sem = Semester.objects.create(
        academic_year=ay,
        number=1,
        start_date=ay.start_date,
        end_date=date(2026, 1, 15),
    )
    # ? is there a way to factor this test in one place
    # and still contentate the type checker mypy?
    assert sem.start_date is not None
    assert sem.end_date is not None

    validate_subperiod(
        sub_start=date(2025, 9, 10),
        sub_end=date(2025, 10, 10),
        container_start=sem.start_date,
        container_end=sem.end_date,
    )


@pytest.mark.django_db
def test_subperiod_end_before_start_raises():
    ay = AcademicYear.objects.create(start_date=date(2025, 9, 1))
    sem = Semester.objects.create(
        academic_year=ay,
        number=1,
        start_date=ay.start_date,
        end_date=date(2026, 1, 15),
    )
    assert sem.start_date is not None
    assert sem.end_date is not None

    with pytest.raises(ValidationError):
        validate_subperiod(
            sub_start=date(2025, 10, 10),
            sub_end=date(2025, 9, 10),
            container_start=sem.start_date,
            container_end=sem.end_date,
        )


@pytest.mark.django_db
def test_subperiod_outside_container_raises():
    ay = AcademicYear.objects.create(start_date=date(2025, 9, 1))
    sem = Semester.objects.create(
        academic_year=ay,
        number=1,
        start_date=ay.start_date,
        end_date=date(2026, 1, 15),
    )
    assert sem.start_date is not None
    assert sem.end_date is not None

    with pytest.raises(ValidationError):
        validate_subperiod(
            sub_start=date(2025, 8, 31),
            sub_end=date(2025, 9, 10),
            container_start=sem.start_date,
            container_end=sem.end_date,
        )


@pytest.mark.django_db
def test_overlapping_subperiod_raises():
    ay = AcademicYear.objects.create(start_date=date(2025, 9, 1))
    sem = Semester.objects.create(
        academic_year=ay,
        number=1,
        start_date=ay.start_date,
        end_date=date(2026, 1, 15),
    )
    Term.objects.create(  # type: ignore[attr-defined]
        semester=sem,
        number=1,
        start_date=date(2025, 9, 1),
        end_date=date(2025, 9, 30),
    )
    assert sem.start_date is not None
    assert sem.end_date is not None

    with pytest.raises(ValidationError):
        overlap_qs = Term.objects.filter(semester=sem)  # type: ignore[attr-defined]
        validate_subperiod(
            sub_start=date(2025, 9, 15),
            sub_end=date(2025, 10, 15),
            container_start=sem.start_date,
            container_end=sem.end_date,
            overlap_qs=overlap_qs,
        )
