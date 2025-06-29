"""Tests for registry grade model."""

from app.registry.models.grade import Grade
import pytest
from django.db import IntegrityError, transaction

pytestmark = pytest.mark.django_db  # replace the @pytest.mark.django_db decorator

# ~~~~~~~~~~~~~~~ DB constraints ~~~~~~~~~~~~~~~~

def test_grade_unique_student_section(student, section):
    """A student only have one grade for a section (the final grade)."""

    Grade.objects.create(
        student=student, section=section, letter_grade="A", numeric_grade=90
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Grade.objects.create(
                student=student, section=section, letter_grade="B", numeric_grade=80
            )
