"""Tests for unique constraints in timetable models."""

import pytest
from django.db import IntegrityError

from app.timetable.models.semester import Semester
from app.timetable.models.term import Term
from app.timetable.models.section import Section
from app.academics.models.program import Program
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.college import College

pytestmark = pytest.mark.django_db


def test_semester_unique_number_per_year(academic_year):
    Semester.objects.create(
        academic_year=academic_year,
        number=1,
        start_date=academic_year.start_date,
        end_date=academic_year.end_date,
    )
    with pytest.raises(IntegrityError):
        Semester.objects.create(
            academic_year=academic_year,
            number=1,
            start_date=academic_year.start_date,
            end_date=academic_year.end_date,
        )


def test_term_unique_number_per_semester(semester):
    Term.objects.create(semester=semester, number=1)
    with pytest.raises(IntegrityError):
        Term.objects.create(semester=semester, number=1)


def test_section_unique_per_program(semester, course):
    curriculum = Curriculum.objects.create(
        short_name="CURSEC",
        long_name="Section Curriculum",
        college=College.get_default(),
    )
    program = Program.objects.create(curriculum=curriculum, course=course)
    Section.objects.create(
        program=program,
        semester=semester,
        number=1,
        start_date=semester.start_date,
        end_date=semester.end_date,
        max_seats=30,
    )
    with pytest.raises(IntegrityError):
        Section.objects.create(
            program=program,
            semester=semester,
            number=1,
            start_date=semester.start_date,
            end_date=semester.end_date,
            max_seats=30,
        )
