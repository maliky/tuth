import pytest
from datetime import date
from app.timetable.models.term import Term
from app.timetable.models.semester import Semester
from app.timetable.models.academic_year import AcademicYear


@pytest.mark.django_db
def test_term_crud():
    """CRUD operations for Term."""
    year = AcademicYear.objects.create(start_date=date(2025, 9, 1))
    semester = Semester.objects.create(
        academic_year=year,
        number=1,
        start_date=year.start_date,
        end_date=date(2026, 1, 15),
    )
    term = Term.objects.create(semester=semester, number=1)
    assert Term.objects.filter(pk=term.pk).exists()

    fetched = Term.objects.get(pk=term.pk)
    assert fetched == term

    fetched.number = 2
    fetched.save()
    updated = Term.objects.get(pk=term.pk)
    assert updated.number == 2

    updated.delete()
    assert not Term.objects.filter(pk=term.pk).exists()
