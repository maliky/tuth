import pytest

from app.academics.models.course import Course
from app.academics.models.program import Program
from app.academics.models.prerequisite import Prerequisite
from app.people.models.student import Student
from app.registry.models.grade import Grade
from app.timetable.models.section import Section


@pytest.mark.django_db
def test_allowed_courses(student: Student, semester):
    course_a = Course.objects.create(number="101")
    course_b = Course.objects.create(number="102")
    Program.objects.create(curriculum=student.curriculum, course=course_a)
    Program.objects.create(curriculum=student.curriculum, course=course_b)
    Prerequisite.objects.create(
        course=course_b, prerequisite_course=course_a, curriculum=student.curriculum
    )
    prog_a = Program.objects.get(course=course_a, curriculum=student.curriculum)
    sec_a = Section.objects.create(program=prog_a, semester=semester, number=1)
    Grade.objects.create(
        student=student, section=sec_a, letter_grade="A", numeric_grade=90
    )

    allowed = list(student.allowed_courses())
    assert course_b in allowed
    assert course_a not in allowed
