"""Tests for the academic :class:`College` model."""

from datetime import date

import pytest
from django.contrib.auth.models import User

from app.academics.models.college import College
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.academics.models.course import Course
from app.academics.models.program import Program
from app.registry.models.grade import Grade, GradeValue
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester
from app.timetable.models.section import Section
from app.academics.choices import CREDIT_NUMBER
from app.people.models.staffs import Staff, Faculty
from app.people.models.student import Student
from app.people.models.role_assignment import RoleAssignment
from app.people.choices import UserRole


pytestmark = pytest.mark.django_db


def test_college_computed_fields():
    """College properties return expected aggregate information."""

    college = College.objects.create(code="COAS")
    dept = Department.objects.create(short_name="SCI", college=college)
    curr1 = Curriculum.objects.create(short_name="CUR1", college=college)
    Curriculum.objects.create(short_name="CUR2", college=college)
    courses = [
        Course.objects.create(department=dept, number=n)
        for n in ["101", "102", "201", "202"]
    ]
    programs = [
        Program.objects.create(
            course=c, curriculum=curr1, credit_hours=CREDIT_NUMBER.TEN
        )
        for c in courses
    ]
    year = AcademicYear.objects.create(start_date=date(2024, 9, 1))
    sem = Semester.objects.create(academic_year=year, number=1)
    sections = [
        Section.objects.create(program=p, semester=sem, number=1)
        for p in programs
    ]

    staff = Staff.objects.create(user=User.objects.create(username="fac"))
    Faculty.objects.create(staff_profile=staff, college=college)

    chair_user = User.objects.create(username="chair", first_name="C", last_name="H")
    RoleAssignment.objects.create(
        user=chair_user,
        role=UserRole.CHAIR,
        college=college,
        department=dept,
        start_date=date.today(),
    )

    student = Student.objects.create(
        user=User.objects.create(username="stud"), curriculum=curr1
    )
    grade_value = GradeValue.objects.create(code="A")
    for sec in sections:
        Grade.objects.create(student=student, section=sec, value=grade_value)

    assert college.faculty_count == 1
    assert college.course_count == 4
    assert "CUR1" in college.curricula_names
    assert "SCI" in college.department_chairs
    assert "sophomore: 1" in college.student_counts_by_level
