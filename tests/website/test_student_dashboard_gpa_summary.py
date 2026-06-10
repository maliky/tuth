"""Student dashboard GPA and transcript-credit regressions."""

from __future__ import annotations

from django.urls import reverse
import pytest

from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.department import Department
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import set_primary_std_curri_enroll
from app.registry.models.credit_hours import CreditHour
from app.registry.models.grade import Grade, GradeValue
from app.timetable.models.section import Section

pytestmark = pytest.mark.django_db


def _history_section(semester, code: str, title: str) -> Section:
    """Create one legacy-history section for dashboard transcript tests."""
    dept = Department.get_dft("HIST")
    course, _ = Course.objects.get_or_create(
        department=dept,
        number=code,
        defaults={"title": title},
    )
    if course.title != title:
        course.title = title
        course.save(update_fields=["title"])
    curriculum = Curriculum.get_dft("BA-HIST-LEGACY")
    curriculum_course, _ = CurriCrs.objects.get_or_create(
        curriculum=curriculum,
        course=course,
        defaults={"credit_hours": CreditHour.objects.get(code=3)},
    )
    return Section.objects.create(
        semester=semester,
        curriculum_course=curriculum_course,
        number=1,
    )


def test_student_dashboard_gpa_uses_effective_legacy_grades_without_double_count(
    client,
    curriculum,
    sem_factory,
    user_factory,
) -> None:
    """Dashboard GPA should not require primary curriculum/registrations to match."""
    semester = sem_factory(1)
    user = user_factory("student_dashboard_legacy_gpa")
    student = Student(user=user, last_enrolled_semester=semester)
    student.save()
    set_primary_std_curri_enroll(student, curriculum)
    grade_a = GradeValue.objects.get_or_create(code="a")[0]
    grade_b = GradeValue.objects.get_or_create(code="b")[0]

    hist101 = _history_section(semester, "101", "Liberian History")
    hist201 = _history_section(semester, "201", "Liberian History and Society")
    hist202 = _history_section(semester, "202", "World History")
    Grade.objects.create(student=student, section=hist101, value=grade_b)
    Grade.objects.create(student=student, section=hist201, value=grade_b)
    Grade.objects.create(student=student, section=hist202, value=grade_a)

    client.force_login(user)
    response = client.get(reverse("student_dashboard"))

    assert response.status_code == 200
    assert b"Cumulative GPA" in response.content
    assert b">3.50<" in response.content
    assert b"Validated credits: 6" in response.content
