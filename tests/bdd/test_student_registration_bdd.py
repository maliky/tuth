"""BDD coverage for student registration and invoice creation."""

from __future__ import annotations

import pytest
from django.urls import reverse
from pytest_bdd import given, scenario, then, when
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait

from app.finance.models.invoice import Invoice
from app.people.models.student import Student
from app.registry.models.registration import Registration
from app.timetable.models.semester import SemesterStatus
from tests.bdd.fixtures import StudentContext
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
def test_student_registration_bdd():
    """Drive student registration from the dashboard."""


@given("a student with an open registration semester")
def student_with_open_registration_semester(
    student_context: StudentContext,
    portal_user_factory,
    registrar_semester_pair_factory,
) -> None:
    """Provision a student tied to a semester that is open for registration."""
    _academic_year, _previous, current = registrar_semester_pair_factory()
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
    student_context.user = user
    student_context.semester = current
    student_context.student = student


@given("a curriculum section available for registration")
def curriculum_section_available(
    student_context: StudentContext,
    registrar_section_factory,
) -> None:
    """Create an eligible section in the student's curriculum."""
    assert student_context.semester is not None
    section, curriculum = registrar_section_factory(student_context.semester)
    student = student_context.student
    assert student is not None
    student.curriculum = curriculum
    student.save(update_fields=["curriculum"])
    student_context.section = section
    student_context.fee_due = section.fee_total_amount()


@when("the student selects the section and saves the registration")
def student_saves_registration(
    student_context: StudentContext,
    selenium_driver,
    live_server,
) -> None:
    """Select a section from the dashboard and submit the registration."""
    assert student_context.user is not None
    assert student_context.section is not None
    section = student_context.section
    _login_to_portal(selenium_driver, live_server, student_context.user.username)
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
    student_context: StudentContext,
    selenium_driver,
) -> None:
    """Ensure the registration produces a consistent invoice total."""
    assert student_context.student is not None
    assert student_context.section is not None
    assert student_context.fee_due is not None
    section = student_context.section

    def _registration_exists() -> bool:
        return Registration.objects.filter(
            student=student_context.student,
            section=section,
        ).exists()

    WebDriverWait(selenium_driver, 10).until(lambda _driver: _registration_exists())
    invoice = Invoice.objects.get(
        student=student_context.student,
        curriculum_course=student_context.section.curriculum_course,
        semester=student_context.section.semester,
    )
    assert invoice.initial_amount_due == student_context.fee_due
    assert invoice.balance == student_context.fee_due
