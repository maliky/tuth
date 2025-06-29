"""Tests for timetable section model."""

import pytest
from django.db import IntegrityError, transaction

from app.timetable.models.section import Section

pytestmark = pytest.mark.django_db

# ~~~~~~~~~~~~~~~~ DB Constraints ~~~~~~~~~~~~~~~~


def test_section_unique_per_program(program, semester):

    Section.objects.create(semester=semester, program=program, number=1)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Section.objects.create(semester=semester, program=program, number=1)
