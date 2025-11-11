"""Tests for timetable semester model."""
import pytest
from django.db import IntegrityError, transaction

from app.timetable.models.semester import Semester

pytestmark = pytest.mark.django_db

# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


def test_semester_unique_number_per_year(academic_year):
    """In one academic year, we only have one semester."""
    Semester.objects.create(
        academic_year=academic_year,
        number=1,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Semester.objects.create(
                academic_year=academic_year,
                number=1,
            )
