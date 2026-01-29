"""BDD coverage for student dashboard sidebar navigation."""

from __future__ import annotations

import pytest
from django.urls import reverse
from pytest_bdd import given, scenario, then, when
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.timetable.models.semester import Semester
from tests.bdd.fixtures import StudentContext
from tests.selenium.test_portal_roles import _login_to_portal


pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.selenium,
]


@scenario(
    "bdd/features/student_dashboard_links.feature",
    "Student can open invoice and payment statements",
)
def test_student_dashboard_links_bdd():
    """Drive the student dashboard link flow via BDD steps."""


@given("a student with an active semester")
def student_with_active_semester(
    student_context: StudentContext, portal_user_factory, semester: Semester
) -> None:
    """Provision a student tied to the current academic term."""
    user = portal_user_factory("student_links_bdd", student=True, groups=[])
    student_context.user = user
    student_context.semester = semester


@when("the student logs in to the portal")
def student_logs_in(
    student_context: StudentContext, selenium_driver, live_server
) -> None:
    """Log in and open the student dashboard."""
    assert student_context.user is not None
    _login_to_portal(selenium_driver, live_server, student_context.user.username)
    selenium_driver.get(f"{live_server.url}{reverse('student_dashboard')}")


@then("the sidebar shows invoice and payment statement links")
def sidebar_links_present(student_context: StudentContext, selenium_driver) -> None:
    """Ensure sidebar links are present for invoices and payments."""
    assert student_context.semester is not None
    invoice_path = reverse("student_invoice_statement")
    payment_path = reverse("student_payment_receipt", args=[student_context.semester.id])

    selenium_driver.find_element(
        By.CSS_SELECTOR, f".portal-nav a[href$='{invoice_path}']"
    )
    selenium_driver.find_element(
        By.CSS_SELECTOR, f".portal-nav a[href$='{payment_path}']"
    )


@when("the student opens the invoice statement")
def open_invoice_statement(selenium_driver) -> None:
    """Open the invoice statement from the sidebar."""
    invoice_path = reverse("student_invoice_statement")
    selenium_driver.find_element(
        By.CSS_SELECTOR, f".portal-nav a[href$='{invoice_path}']"
    ).click()


@then("the invoice statement page is shown")
def invoice_statement_visible(selenium_driver) -> None:
    """Wait for the invoice statement heading."""
    WebDriverWait(selenium_driver, 10).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "h1"), "Invoice Statement")
    )


@when("the student opens the payment receipt")
def open_payment_receipt(
    student_context: StudentContext, selenium_driver, live_server
) -> None:
    """Open the payment receipt link."""
    assert student_context.semester is not None
    receipt_path = reverse("student_payment_receipt", args=[student_context.semester.id])
    selenium_driver.get(f"{live_server.url}{receipt_path}")


@then("the payment receipt page is shown")
def payment_receipt_visible(selenium_driver) -> None:
    """Wait for the payment receipt heading."""
    WebDriverWait(selenium_driver, 10).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "h1"), "Payment Receipt")
    )
