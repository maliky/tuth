"""Behavioral tests for registrar grades dashboard UI."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum_course import CurriculumCourse
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.people.models.student import Student
from app.shared.models import CreditHour
from app.timetable.models.section import Section
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester
from app.website.views import registrar as registrar_views
from app.registry.models.grade import GradeValue
from tests.selenium.test_landing_page import _can_bind_localhost
from tests.selenium.test_portal_roles import TEST_PASSWORD, _login_to_portal

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.selenium,
]

if not _can_bind_localhost():
    pytestmark.append(
        pytest.mark.skip(
            reason="Selenium tests require permission to bind localhost sockets."
        )
    )


def _create_registrar_user(username: str):
    """Create a registrar user with grade view permission."""
    UserModel = get_user_model()
    user = UserModel.objects.create_user(username=username)
    user.set_password(TEST_PASSWORD)
    user.save()
    perm = Permission.objects.get(codename="view_grade")
    user.user_permissions.add(perm)
    return user


def _create_semesters() -> tuple[AcademicYear, Semester, Semester]:
    """Create previous/current semesters based on today's date."""
    today = timezone.now().date()
    academic_year = AcademicYear.get_default(today)
    previous_semester = Semester.objects.create(
        academic_year=academic_year,
        number=1,
        # > defaut start and end date  should be set based on number and academic year
        start_date=today - timedelta(days=90),
    )
    current_semester = Semester.objects.create(
        academic_year=academic_year,
        number=2,
        # > defaut start and end date should be set based on number and academic year
        start_date=today - timedelta(days=10),
    )
    return academic_year, previous_semester, current_semester


def _create_section_for_semester(semester: Semester):
    """Create a curriculum course section for the supplied semester."""
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
        number="101",
        title="Intro to Accounting",
    )
    credit_hours: CreditHour
    credit_hours, _ = CreditHour.objects.get_or_create(code=3, defaults={"label": "3"})
    curriculum_course: CurriculumCourse = baker.make(
        "academics.CurriculumCourse",
        curriculum=curriculum,
        course=course,
        credit_hours=credit_hours,
    )
    section: Section = baker.make(
        "timetable.Section",
        semester=semester,
        curriculum_course=curriculum_course,
        number=1,
    )
    return section, curriculum


def _create_student_grade(section, curriculum, username: str):
    """Create a student and grade record tied to the provided section."""
    UserModel = get_user_model()
    student_user = UserModel.objects.create_user(username=username)
    student: Student = baker.make(
        "people.Student",
        user=student_user,
        curriculum=curriculum,
        entry_semester=section.semester,
        last_enrolled_semester=section.semester,
    )
    grade_value = GradeValue.get_default()
    baker.make("registry.Grade", student=student, section=section, value=grade_value)
    return student


def test_registrar_grades_defaults_to_current_semester(
    live_server,
    selenium_driver,
):
    """Dashboard semester filter should default to the current semester."""
    academic_year, _previous, current = _create_semesters()
    section, curriculum = _create_section_for_semester(current)
    _create_student_grade(section, curriculum, "student_one")
    registrar_user = _create_registrar_user("registrar_default_semester")

    _login_to_portal(selenium_driver, live_server, registrar_user.username)
    selenium_driver.get(f"{live_server.url}{reverse('registrar_grades_dashboard')}")

    expected_semester = Semester.get_current_semester()
    expected_label = (
        f"{expected_semester.academic_year.code} · Semester {expected_semester.number}"
    )
    WebDriverWait(selenium_driver, 10).until(
        EC.presence_of_element_located((By.NAME, "semester"))
    )
    select = selenium_driver.find_element(By.NAME, "semester")
    selected = select.find_element(By.CSS_SELECTOR, "option:checked")
    assert selected.text.strip() == expected_label


def test_registrar_grades_dashboard_link_and_row_expand(
    live_server,
    selenium_driver,
):
    """Dashboard link should be visible and student rows should expand."""
    _academic_year, _previous, current = _create_semesters()
    section, curriculum = _create_section_for_semester(current)
    student = _create_student_grade(section, curriculum, "student_two")
    registrar_user = _create_registrar_user("registrar_row_click")

    _login_to_portal(selenium_driver, live_server, registrar_user.username)
    selenium_driver.get(f"{live_server.url}{reverse('registrar_grades_dashboard')}")

    selenium_driver.find_element(By.LINK_TEXT, "Back to dashboard")

    toggle = selenium_driver.find_element(
        By.CSS_SELECTOR, f"button[data-bs-target='#student-{student.id}']"
    )
    toggle.click()

    def _row_expanded(driver):
        target = driver.find_element(By.ID, f"student-{student.id}")
        return "show" in target.get_attribute("class").split()

    WebDriverWait(selenium_driver, 10).until(_row_expanded)


@pytest.fixture
def tiny_paginator(monkeypatch: pytest.MonkeyPatch):
    """Force the registrar dashboard to paginate after one record."""

    class TinyPaginator(Paginator):
        """Paginator that ignores the requested per-page size."""

        def __init__(self, object_list, per_page, **kwargs):
            super().__init__(object_list, 1, **kwargs)

    monkeypatch.setattr(registrar_views, "Paginator", TinyPaginator)


def test_registrar_grades_pagination_shows_counts_and_last_link(
    live_server,
    selenium_driver,
    tiny_paginator,
):
    """Pagination should show counts and include a Last link."""
    _academic_year, _previous, current = _create_semesters()
    section, curriculum = _create_section_for_semester(current)
    _create_student_grade(section, curriculum, "student_three")
    _create_student_grade(section, curriculum, "student_four")
    registrar_user = _create_registrar_user("registrar_pagination")

    _login_to_portal(selenium_driver, live_server, registrar_user.username)
    selenium_driver.get(f"{live_server.url}{reverse('registrar_grades_dashboard')}")

    WebDriverWait(selenium_driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".pagination"))
    )
    assert "records" in selenium_driver.page_source
    assert "pages" in selenium_driver.page_source

    last_link = selenium_driver.find_element(By.LINK_TEXT, "Last")
    last_href = last_link.get_attribute("href")
    assert "page=2" in last_href


def test_registrar_grades_transcript_button(
    live_server,
    selenium_driver,
):
    """Summary row should link to the official grade transcript preview."""
    _academic_year, _previous, current = _create_semesters()
    section, curriculum = _create_section_for_semester(current)
    student = _create_student_grade(section, curriculum, "student_transcript")
    registrar_user = _create_registrar_user("registrar_transcript")

    _login_to_portal(selenium_driver, live_server, registrar_user.username)
    selenium_driver.get(f"{live_server.url}{reverse('registrar_grades_dashboard')}")

    transcript_link = selenium_driver.find_element(By.LINK_TEXT, "Official transcript")
    transcript_link.click()

    WebDriverWait(selenium_driver, 10).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "h1"), "Official grade transcript")
    )
    assert student.student_id in selenium_driver.page_source


def test_registrar_grades_go_to_preserves_semester(
    live_server,
    selenium_driver,
    tiny_paginator,
):
    """Go-to pagination should keep the semester filter in the form."""
    _academic_year, _previous, current = _create_semesters()
    section, curriculum = _create_section_for_semester(current)
    _create_student_grade(section, curriculum, "student_page_one")
    _create_student_grade(section, curriculum, "student_page_two")
    registrar_user = _create_registrar_user("registrar_pagination_filter")

    _login_to_portal(selenium_driver, live_server, registrar_user.username)
    dashboard_path = reverse("registrar_grades_dashboard")
    url = f"{live_server.url}{dashboard_path}?semester={current.id}"
    selenium_driver.get(url)

    WebDriverWait(selenium_driver, 10).until(
        EC.presence_of_element_located((By.ID, "pagination-page"))
    )
    hidden_semester = selenium_driver.find_element(
        By.CSS_SELECTOR, "form input[type=hidden][name='semester']"
    )
    assert hidden_semester.get_attribute("value") == str(current.id)
