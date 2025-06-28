"""Tests for DB unique constraints in Academics models."""

import pytest
from django.db import IntegrityError

from app.academics.models.curriculum import Curriculum
from app.academics.models.college import College
from app.academics.models.department import Department
from app.academics.models.course import Course
from app.academics.models.program import Program
from app.academics.models.prerequisite import Prerequisite

pytestmark = pytest.mark.django_db


def test_department_unique_short_name_in_college(department_factory, college):
    """In a College a department short_name should be unique."""
    dept = department_factory(short_name="GEN", college=college)
    Department.objects.create(
    with pytest.raises(IntegrityError):
        Department.objects.create(code="D2", short_name="GEN", college=college)


def test_course_number_per_department(department):
    Course.objects.create(department=department, number="101")
    with pytest.raises(IntegrityError):
        Course.objects.create(department=department, number="101")


def test_program_unique_course_per_curriculum(course):
    curriculum = Curriculum.objects.create(
        short_name="UNIQCUR",
        long_name="Unique Curriculum",
        college=College.get_default(),
    )
    Program.objects.create(curriculum=curriculum, course=course)
    with pytest.raises(IntegrityError):
        Program.objects.create(curriculum=curriculum, course=course)


def test_prerequisite_unique_per_curriculum(department_factory, course_factory):
    curriculum = Curriculum.objects.create(
        short_name="CURPRQ",
        long_name="Curriculum for prereqs",
        college=College.get_default(),
    )
    dept = department_factory()
    c1 = course_factory(dept, "201")
    c2 = course_factory(dept, "202")
    
    Prerequisite.objects.create(curriculum=curriculum, course=c2, prerequisite_course=c1)
    
    with pytest.raises(IntegrityError):
        Prerequisite.objects.create(
            curriculum=curriculum, course=c2, prerequisite_course=c1
        )


def test_prerequisite_no_self(course):
    curriculum = Curriculum.objects.create(
        short_name="CURSELF",
        long_name="Curriculum self prereq",
        college=College.get_default(),
    )
    with pytest.raises(IntegrityError):
        Prerequisite.objects.create(
            curriculum=curriculum,
            course=course,
            prerequisite_course=course,
        )
