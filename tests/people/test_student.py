"""Test student people module."""

import pytest
from django.utils import timezone
from datetime import datetime

from app.academics.models.prerequisite import Prerequisite
from app.people.models.student import Student
from app.registry.models.grade import Grade, GradeValue
from app.timetable.models.section import Section


@pytest.mark.django_db
def test_allowed_courses(student: Student, semester, program_factory):
    """We test that if a course A is a prerequisite to course B.

    then A must be passed to see B in allowed courses for the student.
    """
    program_a = program_factory("101", student.curriculum.short_name)
    program_b = program_factory("102", student.curriculum.short_name)
    course_a = program_a.course
    course_b = program_b.course

    Prerequisite.objects.create(
        course=course_b, prerequisite_course=course_a, curriculum=student.curriculum
    )

    sec_a = Section.objects.create(program=program_a, semester=semester, number=1)

    allowed_initial = list(student.allowed_courses())

    assert course_a in allowed_initial

    grade_value = GradeValue.objects.create(code="A")
    Grade.objects.create(student=student, section=sec_a, value=grade_value)

    allowed = list(student.allowed_courses())

    assert course_b in allowed
    assert course_a not in allowed


@pytest.mark.django_db
def test_student_save_assigns_group(curriculum, student_factory):
    """Saving a Student shoul add the user to the student group."""
    stud = student_factory("newstud", curriculum.short_name)

    assert stud.user.groups.filter(name=stud.GROUP).exists()


@pytest.mark.django_db
def test_first_enrollment_date_set_on_confirmation(student_factory, curriculum, semester):
    """Saving after confirming enrollment sets the first date."""
    student = student_factory("fresh", curriculum.short_name)
    assert student.first_enrollment_date is None

    student.current_enrolled_semester = semester
    student.save()

    assert student.first_enrollment_date == timezone.localdate()


@pytest.mark.django_db
def test_first_enrollment_date_not_overwritten(student: Student, semester_factory):
    """Updating enrollment later should keep the original date."""
    original_date = student.first_enrollment_date
    new_semester = semester_factory(2, datetime(2031, 9, 1))
    student.current_enrolled_semester = new_semester
    student.save()

    assert student.first_enrollment_date == original_date
