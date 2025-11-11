"""Tests for timetable term model."""
import pytest
from django.db import IntegrityError, transaction

from app.timetable.models.term import Term

pytestmark = pytest.mark.django_db

# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


def test_term_unique_number_per_semester(semester):
    Term.objects.create(semester=semester, number=1)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Term.objects.create(semester=semester, number=1)
