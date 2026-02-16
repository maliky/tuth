"""Tests for registry grade model."""

from app.registry.models.grade import Grade, GradeValue
import pytest
from django.db import IntegrityError, transaction

pytestmark = pytest.mark.django_db  # replace the @pytest.mark.django_db decorator

# ~~~~~~~~~~~~~~~ DB constraints ~~~~~~~~~~~~~~~~


def test_grade_unique_std_sec(std_factory, sec_factory):
    """A student only have one grade for a section (the final grade)."""
    student = std_factory("grad_student", "TestCURRI")
    section = sec_factory("007", "TestCURRI")
    grade_a = GradeValue.objects.create(code="A")
    grade_b = GradeValue.objects.create(code="B")

    Grade.objects.create(student=student, section=section, value=grade_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Grade.objects.create(student=student, section=section, value=grade_b)
