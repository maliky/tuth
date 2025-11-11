"""Test student people module."""

import pytest

from app.academics.models.prerequisite import Prerequisite
from app.people.models.student import Student
from app.registry.models.grade import Grade, GradeValue
from app.timetable.models.section import Section


@pytest.mark.django_db
def test_allowed_courses(student: Student, semester, curriculum_course_factory):
    """We test that if a course A is a prerequisite to course B.

    then A must be passed to see B in allowed courses for the student.
    """
    curriculum_course_a = curriculum_course_factory("101", student.curriculum.short_name)
    curriculum_course_b = curriculum_course_factory("102", student.curriculum.short_name)
    course_a = curriculum_course_a.course
    course_b = curriculum_course_b.course

    Prerequisite.objects.create(
        course=course_b, prerequisite_course=course_a, curriculum=student.curriculum
    )

    sec_a = Section.objects.create(
        curriculum_course=curriculum_course_a, semester=semester, number=1
    )

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
