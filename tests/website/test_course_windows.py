"""Tests for course selection windows and student dashboard behavior."""
from datetime import date

import pytest
from django.contrib.auth.models import Permission, User
from django.urls import reverse
from model_bakery import baker

from app.shared.models import CreditHour
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester, SemesterStatus
from app.academics.models.college import College
from app.academics.models.course import Course, CurriculumCourse
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department


def _ensure_semester_statuses():
    """Make sure the canonical semester statuses exist."""
    for code, label in [
        ("planning", "Planning"),
        ("registration", "Registration Open"),
        ("locked", "Locked"),
    ]:
        SemesterStatus.objects.get_or_create(code=code, defaults={"label": label})


@pytest.mark.django_db
def test_student_dashboard_prefers_open_semester(client):
    """Student dashboard should show the semester with an open status."""
    _ensure_semester_statuses()

    academic_year: AcademicYear = baker.make(
        "timetable.AcademicYear",
        start_date=date(2025, 7, 1),
        end_date=date(2026, 6, 30),
    )
    current_sem: Semester = baker.make(
        "timetable.Semester", academic_year=academic_year, number=1
    )
    next_sem: Semester = baker.make(
        "timetable.Semester", academic_year=academic_year, number=2
    )

    college: College = baker.make("academics.College")
    department: Department = baker.make("academics.Department", college=college)
    curriculum: Curriculum = baker.make(
        "academics.Curriculum",
        college=college,
        short_name="BBA",
        long_name="BBA Accounting",
    )
    course: Course = baker.make(
        "academics.Course",
        department=department,
        number="201",
        title="Principles of Accounting",
    )
    credit_hours, _ = CreditHour.objects.get_or_create(code=3, defaults={"label": "3"})
    curriculum_course: CurriculumCourse = baker.make(
        "academics.CurriculumCourse",
        curriculum=curriculum,
        course=course,
        credit_hours=credit_hours,
    )
    baker.make(
        "timetable.Section", semester=next_sem, curriculum_course=curriculum_course
    )

    student_user = baker.make(User, username="stud1")
    baker.make(
        "people.Student",
        user=student_user,
        curriculum=curriculum,
        current_enrolled_semester=current_sem,
    )

    next_sem.status_id = "registration"
    next_sem.save(update_fields=["status"])

    client.force_login(student_user)
    response = client.get(reverse("student_dashboard"))

    assert response.status_code == 200
    assert response.context["current_semester"] == next_sem
    assert response.context["registration_open"] is True
    available = response.context["available_courses"]
    assert any(course["sections"] for course in available)


@pytest.mark.django_db
def test_registrar_dashboard_toggles_window(client):
    """Registrar dashboard should update semester status."""
    _ensure_semester_statuses()

    academic_year: AcademicYear = baker.make(
        "timetable.AcademicYear",
        start_date=date(2025, 7, 1),
        end_date=date(2026, 6, 30),
    )
    semester: Semester = baker.make(
        "timetable.Semester", academic_year=academic_year, number=1
    )

    registrar = baker.make(User, username="registrar")
    perm = Permission.objects.get(codename="change_semester")
    registrar.user_permissions.add(perm)
    client.force_login(registrar)

    response = client.post(
        reverse("registrar_course_windows"),
        {"semester_id": semester.id, "status_code": "registration"},
        follow=True,
    )

    assert response.status_code == 200
    semester.refresh_from_db()
    assert semester.status_id == "registration"
