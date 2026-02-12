"""Shared registrar/grades fixtures for Selenium and BDD tests."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, TypeAlias, cast

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.utils import timezone

from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCourse
from app.people.models.student import Student
from app.registry.models.grade import Grade, GradeValue
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester, SemesterStatus
from tests.selenium.fixtures_portal import TEST_PASSWORD

RegUserFactoryT: TypeAlias = Callable[[str], object]
RegSemesterPairFactoryT: TypeAlias = Callable[
    [date | None, int, int], tuple[AcademicYear, Semester, Semester]
]
RegSectionFactoryT: TypeAlias = Callable[[Semester, str, str], tuple[Section, Curriculum]]
RegStdFactoryT: TypeAlias = Callable[[str, Curriculum, Semester], Student]
RegGradeFactoryT: TypeAlias = Callable[[Student, Section], Grade]


@pytest.fixture
def registrar_user_factory() -> RegUserFactoryT:
    """Return a callable to build registrar users with grade permissions."""
    UserModel = get_user_model()
    permission = Permission.objects.get(codename="view_grade")

    def _make(username: str):
        user, _created = UserModel.objects.get_or_create(username=username)
        user.set_password(TEST_PASSWORD)
        user.save()
        user.user_permissions.add(permission)
        return user

    return _make


@pytest.fixture
def registrar_semester_pair_factory() -> RegSemesterPairFactoryT:
    """Return a callable to create a previous/current semester pair."""

    def _make(
        today: date | None = None,
        previous_offset_days: int = 90,
        current_offset_days: int = 10,
    ) -> tuple[AcademicYear, Semester, Semester]:
        SemesterStatus._populate_attributes_and_db()
        base_date = today or timezone.now().date()
        academic_year = AcademicYear.get_default(base_date)
        previous = Semester.objects.create(
            academic_year=academic_year,
            number=1,
            start_date=base_date - timedelta(days=previous_offset_days),
        )
        current = Semester.objects.create(
            academic_year=academic_year,
            number=2,
            start_date=base_date - timedelta(days=current_offset_days),
        )
        return academic_year, previous, current

    return _make


@pytest.fixture
def registrar_semester_pair(
    registrar_semester_pair_factory: RegSemesterPairFactoryT,
) -> tuple[AcademicYear, Semester, Semester]:
    """Return a default previous/current semester pair."""
    return registrar_semester_pair_factory(None, 90, 10)


@pytest.fixture
def registrar_section_factory(
    curriculum_course_factory,
    credit_hour_factory,
) -> RegSectionFactoryT:
    """Return a callable to build sections tied to a supplied semester."""

    def _make(
        semester: Semester,
        course_number: str = "101",
        curriculum_short_name: str = "CURRI_TEST",
    ) -> tuple[Section, Curriculum]:
        curriculum_course: CurriCourse = curriculum_course_factory(
            course_number, curriculum_short_name
        )
        if not curriculum_course.credit_hours_id:
            curriculum_course.credit_hours = credit_hour_factory(3)
            curriculum_course.save(update_fields=["credit_hours"])
        section = Section.objects.create(
            semester=semester, curriculum_course=curriculum_course, number=1
        )
        return section, curriculum_course.curriculum

    return _make


@pytest.fixture
def registrar_student_factory() -> RegStdFactoryT:
    """Return a callable to build students for registrar grade flows."""
    UserModel = get_user_model()

    def _make(username: str, curriculum: Curriculum, semester: Semester) -> Student:
        user, _created = UserModel.objects.get_or_create(username=username)
        user.set_password(TEST_PASSWORD)
        user.save()
        student, _created = Student.objects.get_or_create(
            user=user,
            defaults={
                "curriculum": curriculum,
                "entry_semester": semester,
                "last_enrolled_semester": semester,
            },
        )
        return cast(Student, student)

    return _make


@pytest.fixture
def registrar_grade_factory() -> RegGradeFactoryT:
    """Return a callable to create grade records for a student in a section."""

    def _make(student: Student, section: Section) -> Grade:
        grade_value = GradeValue.get_default()
        return Grade.objects.create(student=student, section=section, value=grade_value)

    return _make
