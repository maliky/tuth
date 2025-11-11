"""Tests for the academic :class:`College` model."""
from datetime import date

import pytest
from app.registry.models.grade import Grade, GradeValue
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester
from app.timetable.models.section import Section
from app.people.models.role_assignment import RoleAssignment
from app.shared.auth.perms import UserRole
from app.shared.models import CreditHour


pytestmark = pytest.mark.django_db


def test_college_computed_fields(
    department_factory,
    curriculum_factory,
    curriculum_course_factory,
    faculty,
    user_factory,
    student_factory,
):
    """College properties return expected aggregate information."""
    dept = department_factory("SCI")
    college = dept.college
    curr1 = curriculum_factory("CUR1")
    curriculum_factory("CUR2")
    curriculum_courses = [
        curriculum_course_factory(str(n), curr1.short_name)
        for n in ["101", "102", "201", "202"]
    ]
    for p in curriculum_courses:
        p.credit_hours = CreditHour.objects.get(code=10)
        p.save()
    year = AcademicYear.objects.create(start_date=date(2024, 9, 1))
    sem = Semester.objects.create(academic_year=year, number=1)
    sections = [
        Section.objects.create(curriculum_course=p, semester=sem, number=1)
        for p in curriculum_courses
    ]

    faculty.college = college
    faculty.save()

    chair_user = user_factory("chair")

    RoleAssignment.objects.create(
        user=chair_user,
        group=UserRole.CHAIR.value.group,
        college=college,
        department=dept,
        start_date=date.today(),
    )

    student = student_factory("stud", curr1.short_name)
    grade_value = GradeValue.objects.create(code="A")
    for sec in sections:
        Grade.objects.create(student=student, section=sec, value=grade_value)

    assert college.faculty_count == 1
    assert college.course_count == 4
    assert "CUR1" in college.curricula_names
    assert "SCI" in college.department_chairs
    assert "sophomore: 1" in college.student_counts_by_level
