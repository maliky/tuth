"""Test student people module."""

import pytest
from django.contrib.auth.models import User

from app.academics.models.curriculum import Curriculum
from app.academics.models.prerequisite import Prerequisite
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import set_primary_std_curri_enroll
from app.registry.models.credit_hours import CreditHour
from app.registry.models.grade import Grade, GradeValue
from app.timetable.models.section import Section


def _credit_hour(code: int) -> CreditHour:
    """Return a credit-hour lookup row for tests."""
    credit_hour, _created = CreditHour.objects.get_or_create(
        code=code,
        defaults={"label": str(code)},
    )
    return credit_hour


def _grade_value(code: str) -> GradeValue:
    """Return a grade value with normalized grading metadata."""
    grade_value, _created = GradeValue.objects.get_or_create(code=code.lower())
    return grade_value


def _graded_section(
    student: Student,
    section: Section,
    code: str = "a",
    *,
    is_effective: bool = True,
) -> Grade:
    """Create a grade row, preserving explicit effective state when requested."""
    grade = Grade(
        student=student,
        section=section,
        value=_grade_value(code),
        is_effective=is_effective,
    )
    grade.save(recompute_effective=is_effective)
    return grade


@pytest.mark.django_db
def test_allowed_crss(student: Student, semester, curriculum_course_factory):
    """We test that if a course A is a prerequisite to course B.

    then A must be passed to see B in allowed courses for the student.
    """
    curriculum = student.primary_curriculum
    curriculum_course_a = curriculum_course_factory("101", curriculum.short_name)
    curriculum_course_b = curriculum_course_factory("102", curriculum.short_name)
    course_a = curriculum_course_a.course
    course_b = curriculum_course_b.course

    Prerequisite.objects.create(
        course=course_b, prerequisite_course=course_a, curriculum=curriculum
    )

    sec_a = Section.objects.create(
        curriculum_course=curriculum_course_a, semester=semester, number=1
    )

    allowed_initial = list(student.allowed_crss())

    assert course_a in allowed_initial

    grade_value = GradeValue.objects.create(code="A")
    Grade.objects.create(student=student, section=sec_a, value=grade_value)

    allowed = list(student.allowed_crss())

    assert course_b in allowed
    assert course_a not in allowed


@pytest.mark.django_db
def test_std_save_assigns_gp(curriculum, std_factory):
    """Saving a Student shoul add the user to the student group."""
    stud = std_factory("newstud", curriculum.short_name)

    assert stud.user.groups.filter(name=stud.GROUP).exists()


@pytest.mark.django_db
def test_std_email_uses_username_prefix():
    """Student email prefix matches username; no extra suffixes inserted."""
    student = Student.objects.create(
        first_name="Jane",
        last_name="Doe",
    )
    set_primary_std_curri_enroll(student, Curriculum.get_dft())

    email = student.mk_email()
    assert email.startswith("janedoe"), f"email should start with username, got {email}"
    assert email.endswith(Student.EMAIL_SUFFIX), f"but {email, Student.EMAIL_SUFFIX}"


@pytest.mark.django_db
def test_completed_credits_use_effective_passing_grades_without_curriculum_rows(
    curriculum_course_factory,
    sem_factory,
) -> None:
    """Completed credits should not depend on the current curriculum row."""
    student = Student.objects.create(first_name="Anthony", last_name="Senior")
    student.curriculum_enrollments.all().delete()
    semester = sem_factory(1)

    for index in range(37):
        curriculum_course = curriculum_course_factory(
            f"9{index:02d}",
            "HIST-SENIOR",
        )
        curriculum_course.credit_hours = _credit_hour(3)
        curriculum_course.save(update_fields=["credit_hours"])
        section = Section.objects.create(
            curriculum_course=curriculum_course,
            semester=semester,
            number=1,
        )
        _graded_section(student, section, "a")

    assert student.completed_credits == 111
    assert student.class_level == "senior"


@pytest.mark.django_db
def test_completed_credits_ignore_failures_and_non_effective_attempts(
    curriculum_course_factory,
    sem_factory,
) -> None:
    """Only effective passing grade rows should contribute completed credits."""
    student = Student.objects.create(first_name="Repeat", last_name="Student")
    semester = sem_factory(1)

    passed_course = curriculum_course_factory("701", "GRADE-FILTER")
    passed_course.credit_hours = _credit_hour(3)
    passed_course.save(update_fields=["credit_hours"])
    passed_section = Section.objects.create(
        curriculum_course=passed_course,
        semester=semester,
        number=1,
    )
    _graded_section(student, passed_section, "b")

    failed_course = curriculum_course_factory("702", "GRADE-FILTER")
    failed_course.credit_hours = _credit_hour(3)
    failed_course.save(update_fields=["credit_hours"])
    failed_section = Section.objects.create(
        curriculum_course=failed_course,
        semester=semester,
        number=1,
    )
    _graded_section(student, failed_section, "f")

    stale_course = curriculum_course_factory("703", "GRADE-FILTER")
    stale_course.credit_hours = _credit_hour(3)
    stale_course.save(update_fields=["credit_hours"])
    stale_section = Section.objects.create(
        curriculum_course=stale_course,
        semester=semester,
        number=1,
    )
    _graded_section(student, stale_section, "a", is_effective=False)

    assert student.completed_credits == 3


@pytest.mark.django_db
def test_completed_credits_count_repeated_course_once(
    curriculum_course_factory,
    sem_factory,
) -> None:
    """Repeated courses should count only the latest effective attempt."""
    student = Student.objects.create(first_name="Repeat", last_name="Effective")
    first_semester = sem_factory(1)
    second_semester = sem_factory(2)
    curriculum_course = curriculum_course_factory("704", "GRADE-REPEAT")
    curriculum_course.credit_hours = _credit_hour(3)
    curriculum_course.save(update_fields=["credit_hours"])

    first_section = Section.objects.create(
        curriculum_course=curriculum_course,
        semester=first_semester,
        number=1,
    )
    second_section = Section.objects.create(
        curriculum_course=curriculum_course,
        semester=second_semester,
        number=1,
    )

    first_grade = _graded_section(student, first_section, "c")
    second_grade = _graded_section(student, second_section, "a")

    first_grade.refresh_from_db()
    second_grade.refresh_from_db()
    assert first_grade.is_effective is False
    assert second_grade.is_effective is True
    assert student.completed_credits == 3
