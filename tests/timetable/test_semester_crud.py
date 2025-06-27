import pytest
from datetime import date
from app.timetable.models.semester import Semester
from app.timetable.models.academic_year import AcademicYear


@pytest.mark.django_db
def test_semester_crud():
    """CRUD operations for Semester."""
    year = AcademicYear.objects.create(start_date=date(2025, 9, 1))
    semester = Semester.objects.create(
        academic_year=year,
        number=1,
        start_date=year.start_date,
        end_date=date(2026, 1, 15),
    )
    assert Semester.objects.filter(pk=semester.pk).exists()

    fetched = Semester.objects.get(pk=semester.pk)
    assert fetched == semester

    fetched.number = 2
    fetched.save()
    updated = Semester.objects.get(pk=semester.pk)
    assert updated.number == 2

    updated.delete()
    assert not Semester.objects.filter(pk=semester.pk).exists()
