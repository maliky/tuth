import pytest
from datetime import date
from app.timetable.models.academic_year import AcademicYear


@pytest.mark.django_db
def test_academicyear_crud():
    """CRUD operations for AcademicYear."""
    year = AcademicYear.objects.create(start_date=date(2025, 9, 1))
    assert AcademicYear.objects.filter(pk=year.pk).exists()

    fetched = AcademicYear.objects.get(pk=year.pk)
    assert fetched == year

    fetched.start_date = date(2026, 9, 1)
    fetched.save()
    updated = AcademicYear.objects.get(pk=year.pk)
    assert updated.start_date.year == 2026

    updated.delete()
    assert not AcademicYear.objects.filter(pk=year.pk).exists()
