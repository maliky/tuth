"""Tests for Course participant querysets."""

from datetime import date, timedelta

import pytest

from app.academics.models.course import Course
from app.academics.models.program import Program
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester
from app.timetable.models.section import Section
from app.registry.models.registration import Registration

pytestmark = pytest.mark.django_db


def _setup_course_env(faculty, student_factory, curriculum):
    """Create a course with a section in the current semester."""
    today = date.today()
    start = date(today.year, 8, 1)
    ay = AcademicYear.objects.create(start_date=start)
    semester = Semester.objects.create(
        academic_year=ay,
        number=1,
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=1),
    )
    course = Course.get_unique_default()
    program = Program.objects.create(course=course, curriculum=curriculum)
    section = Section.objects.create(semester=semester, program=program, faculty=faculty)
    student = student_factory("stud1", curriculum.short_name)
    Registration.objects.create(student=student, section=section)
    return course, faculty, student


def test_current_faculty_returns_faculty(faculty, student_factory, curriculum):
    """Course.current_faculty returns faculty for the active semester."""
    course, fac, _student = _setup_course_env(faculty, student_factory, curriculum)
    assert list(course.current_faculty()) == [fac]


def test_current_students_returns_students(faculty, student_factory, curriculum):
    """Course.current_students returns students for the active semester."""
    course, _fac, stud = _setup_course_env(faculty, student_factory, curriculum)
    assert list(course.current_students()) == [stud]
