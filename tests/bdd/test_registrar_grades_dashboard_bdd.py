"""BDD coverage for the registrar grades dashboard."""

from __future__ import annotations

import pytest
from django.urls import reverse
from pytest_bdd import given, scenario, then, when
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from tests.bdd.fixtures import RegContext
from tests.selenium.fixtures_portal import _login_to_portal

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.selenium,
]


@scenario(
    "features/registrar_grades_dashboard.feature",
    "Defaults to most recent semester with graded students",
)
def test_registrar_grades_default_semester_bdd():
    """Drive the default semester scenario."""


@scenario(
    "features/registrar_grades_dashboard.feature",
    "Dashboard link and row expand",
)
def test_registrar_grades_row_expand_bdd():
    """Drive the row expand scenario."""


@scenario(
    "features/registrar_grades_dashboard.feature",
    "Pagination shows counts and last link",
)
def test_registrar_grades_pagination_bdd():
    """Drive the pagination scenario."""


@scenario("features/registrar_grades_dashboard.feature", "Transcript button")
def test_registrar_grades_transcript_bdd():
    """Drive the transcript scenario."""


@scenario("features/registrar_grades_dashboard.feature", "Go-to preserves semester")
def test_registrar_grades_go_to_preserves_bdd():
    """Drive the go-to pagination scenario."""


@given("a registrar user")
def registrar_user(registrar_context: RegContext, registrar_user_factory) -> None:
    """Provision a registrar with grade permissions."""
    registrar_context.user = registrar_user_factory("registrar_bdd")


@given("the registrar data includes graded students in multiple semesters")
def dashboard_has_graded_students_in_multiple_semesters(
    registrar_context: RegContext,
    registrar_semester_pair_factory,
    registrar_section_factory,
    registrar_student_factory,
    registrar_grade_factory,
) -> None:
    """Set up graded students in old/new semesters and keep the latest in context."""
    _academic_year, previous, current = registrar_semester_pair_factory()
    previous_section, previous_curriculum = registrar_section_factory(
        previous,
        course_number="100",
        curriculum_short_name="CURRI_REG_MULTI",
    )
    previous_student = registrar_student_factory(
        "student_bdd_previous",
        previous_curriculum,
        previous,
    )
    registrar_grade_factory(previous_student, previous_section)

    current_section, current_curriculum = registrar_section_factory(
        current,
        course_number="101",
        curriculum_short_name="CURRI_REG_MULTI",
    )
    current_student = registrar_student_factory(
        "student_bdd_current",
        current_curriculum,
        current,
    )
    registrar_grade_factory(current_student, current_section)
    registrar_context.semester = current
    registrar_context.student = current_student


@given("the registrar data includes graded students in the current semester")
def dashboard_has_current_semester(
    registrar_context: RegContext,
    registrar_semester_pair_factory,
    registrar_section_factory,
    registrar_student_factory,
    registrar_grade_factory,
) -> None:
    """Set up one graded student in the latest semester."""
    _academic_year, _previous, current = registrar_semester_pair_factory()
    section, curriculum = registrar_section_factory(current)
    student = registrar_student_factory("student_bdd", curriculum, current)
    registrar_grade_factory(student, section)
    registrar_context.semester = current
    registrar_context.student = student


@given("the grades dashboard has two graded students in the current semester")
def dashboard_has_two_students(
    registrar_context: RegContext,
    registrar_semester_pair_factory,
    registrar_section_factory,
    registrar_student_factory,
    registrar_grade_factory,
    tiny_paginator,
) -> None:
    """Set up two students with grades in the current semester."""
    _academic_year, _previous, current = registrar_semester_pair_factory()
    section, curriculum = registrar_section_factory(current)
    student_one = registrar_student_factory("student_bdd_one", curriculum, current)
    student_two = registrar_student_factory("student_bdd_two", curriculum, current)
    registrar_grade_factory(student_one, section)
    registrar_grade_factory(student_two, section)
    registrar_context.semester = current
    registrar_context.student = student_one


@when("the registrar opens the grades dashboard")
def registrar_opens_dashboard(
    registrar_context: RegContext, live_server, selenium_driver
) -> None:
    """Open the grades dashboard after login."""
    assert registrar_context.user is not None
    _login_to_portal(selenium_driver, live_server, registrar_context.user.username)
    selenium_driver.get(f"{live_server.url}{reverse('registrar_grades_dashboard')}")


@when("the registrar opens the grades dashboard filtered by the current semester")
def registrar_opens_dashboard_filtered(
    registrar_context: RegContext, live_server, selenium_driver
) -> None:
    """Open the grades dashboard with the semester filter applied."""
    assert registrar_context.user is not None
    assert registrar_context.semester is not None
    _login_to_portal(selenium_driver, live_server, registrar_context.user.username)
    dashboard_path = reverse("registrar_grades_dashboard")
    url = f"{live_server.url}{dashboard_path}?semester={registrar_context.semester.id}"
    selenium_driver.get(url)


@then("the semester filter defaults to the most recent semester with graded students")
def semester_filter_defaults(registrar_context: RegContext, selenium_driver) -> None:
    """Verify the default semester selection matches the latest graded semester."""
    assert registrar_context.semester is not None
    expected_semester = registrar_context.semester
    expected_label = (
        f"{expected_semester.academic_year.code} · Semester {expected_semester.number}"
    )
    WebDriverWait(selenium_driver, 10).until(
        EC.presence_of_element_located((By.NAME, "semester"))
    )
    select = selenium_driver.find_element(By.NAME, "semester")
    selected = select.find_element(By.CSS_SELECTOR, "option:checked")
    assert selected.text.strip() == expected_label


@then("the dashboard link is visible")
def dashboard_link_visible(selenium_driver) -> None:
    """Ensure the back-to-dashboard link exists."""
    selenium_driver.find_element(By.LINK_TEXT, "Back to dashboard")


@then("the registrar can expand the student row")
def registrar_can_expand_row(registrar_context: RegContext, selenium_driver) -> None:
    """Expand the row for the prepared student."""
    assert registrar_context.student is not None
    # Cache the id to keep type narrowing inside the nested callback.
    student_id = registrar_context.student.id
    toggle = selenium_driver.find_element(
        By.CSS_SELECTOR,
        f"button[data-bs-target='#student-{student_id}']",
    )
    toggle.click()

    def _row_expanded(driver):
        target = driver.find_element(By.ID, f"student-{student_id}")
        return "show" in target.get_attribute("class").split()

    WebDriverWait(selenium_driver, 10).until(_row_expanded)


@then("the pagination shows counts and last link")
def pagination_shows_counts(selenium_driver) -> None:
    """Verify pagination counts and the Last link."""
    WebDriverWait(selenium_driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".pagination"))
    )
    assert "records" in selenium_driver.page_source
    assert "pages" in selenium_driver.page_source

    last_link = selenium_driver.find_element(By.LINK_TEXT, "Last")
    last_href = last_link.get_attribute("href")
    assert "page=2" in last_href


@then("the official transcript page is shown for the student")
def transcript_page_shown(registrar_context: RegContext, selenium_driver) -> None:
    """Open and verify the transcript preview."""
    assert registrar_context.student is not None
    transcript_link = selenium_driver.find_element(By.LINK_TEXT, "Official transcript")
    transcript_link.click()

    WebDriverWait(selenium_driver, 10).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "h1"), "Official grade transcript")
    )
    assert registrar_context.student.student_id in selenium_driver.page_source


@then("the go-to pagination keeps the semester filter")
def pagination_keeps_semester_filter(
    registrar_context: RegContext, selenium_driver
) -> None:
    """Ensure the hidden semester input preserves the selected semester."""
    assert registrar_context.semester is not None
    WebDriverWait(selenium_driver, 10).until(
        EC.presence_of_element_located((By.ID, "pagination-page"))
    )
    hidden_semester = selenium_driver.find_element(
        By.CSS_SELECTOR, "form input[type=hidden][name='semester']"
    )
    assert hidden_semester.get_attribute("value") == str(registrar_context.semester.id)
