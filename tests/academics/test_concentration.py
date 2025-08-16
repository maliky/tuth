"""Tests for the Academic Concentration model."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from app.shared.models import CreditHour

from app.academics.models.concentration import (
    Major,
    MajorProgram,
    Minor,
    MinorProgram,
)
from app.academics.models.program import Program

pytestmark = pytest.mark.django_db


def test_major_get_default_has_program():
    """Default major should include one program."""

    major = Major.get_default()

    assert major.programs.count() == 1


def test_minor_get_default_has_program():
    """Default minor should include one program."""

    minor = Minor.get_default()

    assert minor.programs.count() == 1


def test_total_credit_hours_sums_programs(major):
    """total_credit_hours should add all attached program credits."""

    pg = Program.get_unique_default()
    pg.credit_hours = CreditHour.objects.get(code=4)
    pg.save()
    major.programs.add(pg)

    total = sum(p.credit_hours_id for p in major.programs.all())

    assert major.total_credit_hours() == total


def test_major_clean_requires_program(curriculum_factory):
    """clean() should fail if no program is attached."""

    curri = curriculum_factory("TEST_CURRI")
    new_major = Major.objects.create(name="NO_PROG", curriculum=curri)

    with pytest.raises(ValidationError):
        new_major.clean()


def test_major_clean_credit_limit_exceeded(major):
    """clean() should detect credit hour overflow."""

    pg = Program.get_unique_default()
    pg.credit_hours = CreditHour.objects.get(code=10)
    pg.save()
    major.programs.add(pg)
    major.max_credit_hours = 5

    with pytest.raises(ValidationError):
        major.clean()


def test_majorprogram_unique_program_per_major(curriculum_factory, program_factory):
    """(major, program) pairs must be unique."""

    major = Major.objects.create(
        name="M_TEST", curriculum=curriculum_factory("M_TEST_CURRI")
    )
    program = program_factory()

    MajorProgram.objects.create(major=major, program=program)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MajorProgram.objects.create(major=major, program=program)


def test_minorprogram_unique_program_per_minor(curriculum_factory, program_factory):
    """(minor, program) pairs must be unique."""

    minor = Minor.objects.create(
        name="MNR_TEST", curriculum=curriculum_factory("MNR_TEST_CURRI")
    )
    program = program_factory()

    MinorProgram.objects.create(minor=minor, program=program)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            MinorProgram.objects.create(minor=minor, program=program)
