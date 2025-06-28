"""Tests for unique constraints in registry models."""

import pytest
from django.db import IntegrityError

from app.registry.models.registration import Registration
from app.registry.models.grade import Grade
from app.academics.models.program import Program
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.college import College
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester

pytestmark = pytest.mark.django_db


def test_registration_unique_student_section(student, semester):
    curriculum = Curriculum.objects.create(
        short_name="CURREG",
        long_name="Registration Curriculum",
        college=College.get_default(),
    )
    course = Course.get_unique_default()
    program = Program.objects.create(curriculum=curriculum, course=course)
    sec = Section.objects.create(
        program=program,
        semester=semester,
        number=1,
        start_date=semester.start_date,
        end_date=semester.end_date,
        max_seats=30,
    )
    Registration.objects.create(student=student, section=sec)
    with pytest.raises(IntegrityError):
        Registration.objects.create(student=student, section=sec)


def test_grade_unique_student_section(student, semester):
    curriculum = Curriculum.objects.create(
        short_name="CURGRD",
        long_name="Grade Curriculum",
        college=College.get_default(),
    )
    course = Course.get_unique_default()
    program = Program.objects.create(curriculum=curriculum, course=course)
    sec = Section.objects.create(
        program=program,
        semester=semester,
        number=1,
        start_date=semester.start_date,
        end_date=semester.end_date,
        max_seats=30,
    )
    Grade.objects.create(
        student=student,
        section=sec,
        letter_grade="A",
        numeric_grade=90,
    )
    with pytest.raises(IntegrityError):
        Grade.objects.create(
            student=student,
            section=sec,
            letter_grade="B",
            numeric_grade=80,
        )
