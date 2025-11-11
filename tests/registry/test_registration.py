"""Tests for registry registration model."""

import pytest
from django.db import IntegrityError, transaction

from app.registry.models.registration import Registration

pytestmark = pytest.mark.django_db  # replace the @pytest.mark.django_db decorator


# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


def test_registration_unique_student_section(student, section):
    """A student can only register once to a section."""
    Registration.objects.create(student=student, section=section)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Registration.objects.create(student=student, section=section)
