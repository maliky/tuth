"""Tests for the Academic Concentration model."""

import pytest
from django.core.exceptions import ValidationError

from app.academics.models.concentration import Major, Minor
from app.academics.models.program import Program
from app.academics.models.curriculum import Curriculum

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
    pg.credit_hours = 4
    pg.save()
    major.programs.add(pg)

    total = sum(p.credit_hours for p in major.programs.all())

    assert major.total_credit_hours() == total


def test_major_clean_requires_program():
    """clean() should fail if no program is attached."""

    curri = Curriculum.get_default("TEST_CURRI")
    new_major = Major.objects.create(name="NO_PROG", curriculum=curri)

    with pytest.raises(ValidationError):
        new_major.clean()


def test_major_clean_credit_limit_exceeded(major):
    """clean() should detect credit hour overflow."""

    pg = Program.get_unique_default()
    pg.credit_hours = 10
    pg.save()
    major.programs.add(pg)
    major.max_credit_hours = 5

    with pytest.raises(ValidationError):
        major.clean()
