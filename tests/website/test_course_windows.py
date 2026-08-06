"""Tests for course selection windows and student dashboard behavior."""

from datetime import date

import pytest
from django.contrib.auth.models import Permission, User
from django.urls import reverse
from model_bakery import baker

from app.academics.choices import AcademicCareer
from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.department import Department
from app.shared.models import CreditHour
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester, SemesterStatus
from app.timetable.graduate_calendar import ensure_graduate_semesters
from app.website.services import registrar_portal
from app.website.services.registrar_portal import group_semester_windows


def _ensure_sem_statuses():
    """Make sure the canonical semester statuses exist."""
    for code, label in [
        ("planning", "Planning"),
        ("registration", "Registration Open"),
        ("grade_entry", "Grade Entry Open"),
        ("running", "Registration Closed, Semester running"),
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
def test_student_dashboard_collapses_registration_history(client, regio_factory):
    """Student registration rows should render inside a collapsed drawer."""
    registration = regio_factory("drawer_student", "CURRI_DRAWER", "250", 1)

    client.force_login(registration.student.user)
    response = client.get(reverse("student_dashboard"))
    content = response.content.decode()

    assert response.status_code == 200
    assert '<details class="student-course-drawer">' in content
    assert "Registrations" in content
    assert "1 course" in content
    assert "data-course-table" in content
    assert content.index("registration-layout") < content.index('id="courses"')
    assert '<details class="student-course-drawer" open' not in content


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
        {
            "semester_id": semester.id,
            "status_code": "registration",
            "academic_career": "undergraduate",
        },
        follow=True,
    )

    assert response.status_code == 200
    semester.refresh_from_db()
    assert semester.status_id == "registration"


@pytest.mark.django_db
def test_semester_career_allows_parallel_undergraduate_and_graduate_windows() -> None:
    """Undergraduate and graduate calendars may reuse year and semester number."""
    academic_year = AcademicYear.objects.create(start_date=date(2026, 8, 1))
    undergraduate = Semester.objects.create(
        academic_year=academic_year,
        number=1,
        academic_career=AcademicCareer.UNDERGRADUATE,
    )
    graduate = Semester.objects.create(
        academic_year=academic_year,
        number=1,
        academic_career=AcademicCareer.GRADUATE,
    )

    assert undergraduate.id != graduate.id
    assert graduate.end_date == date(2027, 1, 31)


@pytest.mark.django_db
def test_open_registration_semester_is_scoped_by_career() -> None:
    """One undergraduate and one graduate semester may both be registration-open."""
    _ensure_sem_statuses()
    academic_year = AcademicYear.objects.create(start_date=date(2026, 8, 1))
    undergraduate = Semester.objects.create(
        academic_year=academic_year,
        number=1,
        academic_career=AcademicCareer.UNDERGRADUATE,
        status_id="registration",
    )
    graduate = Semester.objects.create(
        academic_year=academic_year,
        number=1,
        academic_career=AcademicCareer.GRADUATE,
        status_id="registration",
    )

    assert Semester.regio_open_sem(AcademicCareer.UNDERGRADUATE)[0] == undergraduate
    assert Semester.regio_open_sem(AcademicCareer.GRADUATE)[0] == graduate


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
    """Registrar window page should render foldable undergraduate academic-year groups."""
    _ensure_sem_statuses()
    monkeypatch.setattr(registrar_portal.timezone, "localdate", lambda: date(2026, 3, 1))
    old_year = AcademicYear.objects.create(start_date=date(2024, 8, 1))
    new_year = AcademicYear.objects.create(start_date=date(2025, 8, 1))
    Semester.objects.create(academic_year=old_year, number=1)
    Semester.objects.create(academic_year=new_year, number=2)
    registrar = baker.make(User, username="registrar-window-folding")
    registrar.user_permissions.add(Permission.objects.get(codename="change_semester"))

    client.force_login(registrar)
    response = client.get(
        reverse("reg_crs_wins"),
        {"academic_career": "undergraduate"},
    )

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


@pytest.mark.django_db
def test_reg_window_page_defaults_to_graduate_launch_windows(client) -> None:
    """Course windows should default to the graduate launch years only."""
    _ensure_sem_statuses()
    ensure_graduate_semesters()
    old_year = AcademicYear.objects.create(start_date=date(2025, 8, 1))
    Semester.objects.create(academic_year=old_year, number=1)
    registrar = baker.make(User, username="registrar-window-graduate-default")
    registrar.user_permissions.add(Permission.objects.get(codename="change_semester"))

    client.force_login(registrar)
    response = client.get(reverse("reg_crs_wins"))
    content = response.content.decode()

    assert response.status_code == 200
    assert response.context["selected_academic_career"] == "graduate"
    assert "Graduate semester windows" in content
    assert "26-27" in content
    assert "27-28" in content
    assert "25-26" not in content
    assert 'aria-label="Academic career"' in content
    assert ">Career<" not in content


@pytest.mark.django_db
def test_reg_window_post_preserves_graduate_scope(client) -> None:
    """Updating a graduate semester should redirect back to the graduate view."""
    _ensure_sem_statuses()
    rows = ensure_graduate_semesters()
    semester = next(row[0] for row in rows if row[0].number == 2)
    registrar = baker.make(User, username="registrar-window-graduate-post")
    registrar.user_permissions.add(Permission.objects.get(codename="change_semester"))

    client.force_login(registrar)
    response = client.post(
        reverse("reg_crs_wins"),
        {
            "semester_id": semester.id,
            "status_code": "grade_entry",
            "academic_career": "graduate",
        },
        follow=True,
    )
    semester.refresh_from_db()

    assert response.status_code == 200
    assert response.redirect_chain[-1][0].endswith("?academic_career=graduate")
    assert response.context["selected_academic_career"] == "graduate"
    assert semester.status_id == "grade_entry"
