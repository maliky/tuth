"""Tests for registry grade model."""

from app.registry.models.grade import Grade, GradeType
import pytest
from django.db import IntegrityError, transaction

pytestmark = pytest.mark.django_db  # replace the @pytest.mark.django_db decorator

# ~~~~~~~~~~~~~~~ DB constraints ~~~~~~~~~~~~~~~~


def test_grade_unique_student_section(student, section):
    """A student only have one grade for a section (the final grade)."""

    grade_a = GradeType.objects.create(code="A")
    grade_b = GradeType.objects.create(code="B")
    Grade.objects.create(student=student, section=section, grade=grade_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Grade.objects.create(
                student=student, section=section, grade=grade_b
            )
