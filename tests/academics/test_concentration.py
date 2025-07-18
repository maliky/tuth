"""Tests for the Academic Concentration model."""

import pytest
from django.db import IntegrityError, transaction

from app.academics.models.concentration import (
    Major,
    Minor,
    MajorProgram,
    MinorProgram,
)
from app.academics.models.curriculum import Curriculum
from app.academics.models.program import Program

pytestmark = pytest.mark.django_db


def test_majorprogram_unique_program_per_major():
    """(major, program) pairs must be unique."""

    major = Major.objects.create(name="M_TEST", curriculum=Curriculum.get_default())
    program = Program.get_unique_default()

    MajorProgram.objects.create(major=major, program=program)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MajorProgram.objects.create(major=major, program=program)


def test_minorprogram_unique_program_per_minor():
    """(minor, program) pairs must be unique."""

    minor = Minor.objects.create(name="MNR_TEST", curriculum=Curriculum.get_default())
    program = Program.get_unique_default()

    MinorProgram.objects.create(minor=minor, program=program)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MinorProgram.objects.create(minor=minor, program=program)


