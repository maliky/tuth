"""BDD coverage for student registration and invoice creation."""

from __future__ import annotations

import pytest
from django.urls import reverse
from pytest_bdd import given, scenario, then, when
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait

from app.finance.models.invoice import Invoice
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import set_primary_std_curri_enroll
from app.registry.models.registration import Registration
from app.timetable.models.semester import SemesterStatus
from tests.bdd.fixtures import StdContext
from tests.selenium.fixtures_portal import _login_to_portal


pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.selenium,
]


# In pytest-bdd, a scenario is the executable test case wired to the feature file.
@scenario(
    "features/student_registration.feature",
    "Student registers for an available section",
)
def test_std_regio_bdd():
    """Drive student registration from the dashboard."""


@given("a student with an open registration semester")
def std_with_open_regio_sem(
    std_context: StdContext,
    portal_user_factory,
    reg_sem_pair_factory,
) -> None:
    """Provision a student tied to a semester that is open for registration."""
    _academic_year, _previous, current = reg_sem_pair_factory()
    current.status = SemesterStatus.get_by_code("registration")
    current.save(update_fields=["status"])
    user = portal_user_factory(
        "student_register_bdd",
        student=True,
        groups=[],
        semester_override=current,
    )
    student = Student.objects.get(user=user)
    student.entry_semester = current
    student.last_enrolled_semester = current
    student.save(update_fields=["entry_semester", "last_enrolled_semester"])
    std_context.user = user
    std_context.semester = current
    std_context.student = student


@given("a curriculum section available for registration")
def curri_sec_available(
    std_context: StdContext,
    reg_sec_factory,
) -> None:
    """Create an eligible section in the student's curriculum."""
    assert std_context.semester is not None
    section, curriculum = reg_sec_factory(std_context.semester)
    student = std_context.student
    assert student is not None
    set_primary_std_curri_enroll(student, curriculum)
    std_context.section = section
    std_context.fee_due = section.fee_total_amount()


@when("the student selects the section and saves the registration")
def std_saves_regio(
    std_context: StdContext,
    selenium_driver,
    live_server,
) -> None:
    """Select a section from the dashboard and submit the registration."""
    assert std_context.user is not None
    assert std_context.section is not None
    section = std_context.section
    _login_to_portal(selenium_driver, live_server, std_context.user.username)
    selenium_driver.get(f"{live_server.url}{reverse('student_dashboard')}")

    select_element = selenium_driver.find_element(By.CSS_SELECTOR, ".section-picker")
    Select(select_element).select_by_value(str(section.id))

    selected_input = selenium_driver.find_element(
        By.CSS_SELECTOR, "[data-selected-sections]"
    )
    WebDriverWait(selenium_driver, 10).until(
        lambda _driver: str(section.id) in (selected_input.get_attribute("value") or "")
    )

    selenium_driver.find_element(By.CSS_SELECTOR, "[data-register-submit]").click()
    WebDriverWait(selenium_driver, 10).until(
        lambda _driver: (selected_input.get_attribute("value") or "") == ""
    )


@then("an invoice is created with the initial amount due")
def invoice_created_with_initial_amount_due(
    std_context: StdContext,
    selenium_driver,
) -> None:
    """Ensure the registration produces a consistent invoice total."""
    assert std_context.student is not None
    assert std_context.section is not None
    assert std_context.fee_due is not None
    section = std_context.section

    def _regio_exists() -> bool:
        return Registration.objects.filter(
            student=std_context.student,
            section=section,
        ).exists()

    WebDriverWait(selenium_driver, 10).until(lambda _driver: _regio_exists())
    invoice = Invoice.objects.get(
        student=std_context.student,
        curriculum_course=std_context.section.curriculum_course,
        semester=std_context.section.semester,
    )
    assert invoice.initial_amount_due == std_context.fee_due
    assert invoice.balance == std_context.fee_due
