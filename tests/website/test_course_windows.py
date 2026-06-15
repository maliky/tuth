"""Tests for course selection windows and student dashboard behavior."""

from datetime import date

import pytest
from django.contrib.auth.models import Permission, User
from django.urls import reverse
from model_bakery import baker

from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.department import Department
from app.shared.models import CreditHour
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester, SemesterStatus
from app.website.services import registrar_portal
from app.website.services.registrar_portal import group_semester_windows


def _ensure_sem_statuses():
    """Make sure the canonical semester statuses exist."""
    for code, label in [
        ("planning", "Planning"),
        ("registration", "Registration Open"),
        ("locked", "Locked"),
    ]:
        SemesterStatus.objects.get_or_create(code=code, defaults={"label": label})


@pytest.mark.django_db
def test_std_dashboard_prefers_open_sem(client):
    """Student dashboard should show the semester with an open status."""
    _ensure_sem_statuses()

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
    curriculum_course: CurriCrs = baker.make(
        "academics.CurriCrs",
        curriculum=curriculum,
        course=course,
        credit_hours=credit_hours,
    )
    baker.make(
        "timetable.Section", semester=next_sem, curriculum_course=curriculum_course
    )

    std_user = baker.make(User, username="stud1")
    baker.make(
        "people.Student",
        user=std_user,
        primary_curriculum=curriculum,
        last_enrolled_semester=current_sem,
    )

    next_sem.status_id = "registration"
    next_sem.save(update_fields=["status"])

    client.force_login(std_user)
    response = client.get(reverse("student_dashboard"))

    assert response.status_code == 200
    assert response.context["current_semester"] == next_sem
    assert response.context["registration_open"] is True
    available = response.context["available_courses"]
    assert any(course["sections"] for course in available)


@pytest.mark.django_db
def test_reg_dashboard_toggles_win(client):
    """Registrar dashboard should update semester status."""
    _ensure_sem_statuses()

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
        reverse("reg_crs_wins"),
        {"semester_id": semester.id, "status_code": "registration"},
        follow=True,
    )

    assert response.status_code == 200
    semester.refresh_from_db()
    assert semester.status_id == "registration"


@pytest.mark.django_db
def test_reg_window_groups_are_newest_first() -> None:
    """Registrar window groups should show recent years and semesters first."""
    old_year = AcademicYear.objects.create(start_date=date(2024, 8, 1))
    new_year = AcademicYear.objects.create(start_date=date(2025, 8, 1))
    old_semester = Semester.objects.create(academic_year=old_year, number=1)
    new_semester_one = Semester.objects.create(academic_year=new_year, number=1)
    new_semester_two = Semester.objects.create(academic_year=new_year, number=2)

    groups = group_semester_windows([old_semester, new_semester_one, new_semester_two])

    assert [group["academic_year"] for group in groups] == ["25-26", "24-25"]
    assert [semester.number for semester in groups[0]["semesters"]] == [2, 1]


@pytest.mark.django_db
def test_reg_window_groups_pin_current_year_above_future_year() -> None:
    """Current academic year should stay above future imported years."""
    current_year = AcademicYear.objects.create(start_date=date(2025, 8, 1))
    future_year = AcademicYear.objects.create(start_date=date(2026, 8, 1))
    current_semester = Semester.objects.create(academic_year=current_year, number=3)
    future_semester = Semester.objects.create(academic_year=future_year, number=1)

    groups = group_semester_windows(
        [future_semester, current_semester],
        current_academic_year_id=current_year.id,
    )

    assert [group["academic_year"] for group in groups] == ["25-26", "26-27"]
    assert groups[0]["is_current_academic_year"] is True
    assert groups[0]["semesters"][0] == current_semester


@pytest.mark.django_db
def test_reg_window_groups_current_year_beats_open_non_current_year() -> None:
    """Current academic year should sort above open windows from another year."""
    _ensure_sem_statuses()
    open_year = AcademicYear.objects.create(start_date=date(2024, 8, 1))
    current_year = AcademicYear.objects.create(start_date=date(2025, 8, 1))
    open_semester = Semester.objects.create(
        academic_year=open_year,
        number=1,
        status_id="registration",
    )
    current_semester = Semester.objects.create(academic_year=current_year, number=3)

    groups = group_semester_windows(
        [open_semester, current_semester],
        current_academic_year_id=current_year.id,
    )

    assert [group["academic_year"] for group in groups] == ["25-26", "24-25"]
    assert groups[0]["semesters"][0] == current_semester


@pytest.mark.django_db
def test_reg_window_page_renders_foldable_groups(client, monkeypatch) -> None:
    """Registrar window page should render foldable academic-year groups."""
    _ensure_sem_statuses()
    monkeypatch.setattr(registrar_portal.timezone, "localdate", lambda: date(2026, 3, 1))
    old_year = AcademicYear.objects.create(start_date=date(2024, 8, 1))
    new_year = AcademicYear.objects.create(start_date=date(2025, 8, 1))
    Semester.objects.create(academic_year=old_year, number=1)
    Semester.objects.create(academic_year=new_year, number=2)
    registrar = baker.make(User, username="registrar-window-folding")
    registrar.user_permissions.add(Permission.objects.get(codename="change_semester"))

    client.force_login(registrar)
    response = client.get(reverse("reg_crs_wins"))

    content = response.content.decode()
    assert response.status_code == 200
    assert "<details" in content
    assert "<summary" in content
    assert "registrar-window-group" in content
    assert "Current year" in content
    assert content.index("25-26") < content.index("24-25")
    assert (
        '<details class="portal-accordion-card registrar-window-group mb-3" open>'
        in content
    )
