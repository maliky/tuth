"""Browser-driven mutation smokes for portal staff workflows."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import Select, WebDriverWait

from app.finance.models.payment import Payment
from app.finance.models.status_types_methods import (
    InvoiceStatus,
    Payer,
    PaymentMethod,
    PaymentStatus,
)
from app.people.models.student import Student
from tests.constants import D100
from tests.selenium.fixtures_portal import _login_to_portal

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.selenium,
]


class LiveServerT(Protocol):
    """Minimal live-server fixture protocol used by Selenium tests."""

    url: str


def _ensure_finance_defaults() -> None:
    """Create lookup rows required by finance portal mutations."""
    InvoiceStatus._populate_attributes_and_db()
    PaymentStatus._populate_attributes_and_db()
    PaymentMethod._populate_attributes_and_db()
    Payer._populate_attributes_and_db()


def _perm(codename: str) -> Permission:
    """Return one Django permission by codename."""
    return Permission.objects.get(codename=codename)


def _clear_and_type(element: WebElement, value: str) -> None:
    """Replace the current value in a Selenium input."""
    element.clear()
    element.send_keys(value)


def _set_form_value(driver: WebDriver, element: WebElement, value: str) -> None:
    """Set a possibly hidden form control and notify browser listeners."""
    driver.execute_script(
        """
        arguments[0].value = arguments[1];
        arguments[0].dispatchEvent(new Event("input", { bubbles: true }));
        arguments[0].dispatchEvent(new Event("change", { bubbles: true }));
        """,
        element,
        value,
    )


def _login_fresh(
    driver: WebDriver,
    live_server: LiveServerT,
    username: str,
) -> None:
    """Clear the portal session before authenticating as a test user."""
    driver.get(f"{live_server.url}{reverse('portal_logout')}")
    _login_to_portal(driver, live_server, username)


def test_finance_officer_can_mutate_payments_in_browser(
    live_server,
    selenium_driver,
    portal_user_factory,
    std_invoice_factory,
    semester,
) -> None:
    """Finance officer can create and update payment rows through the portal UI."""
    _ensure_finance_defaults()
    finance_user = portal_user_factory(
        "selenium_finance_mutation",
        groups=["Finance Officer"],
    )
    student_user = portal_user_factory(
        "selenium_finance_student",
        student=True,
    )
    student = Student.objects.get(user=student_user)
    invoice = std_invoice_factory(student, semester, D100)

    _login_fresh(selenium_driver, live_server, finance_user.username)
    invoice_url = (
        f"{live_server.url}{reverse('finance_officer_invoices')}"
        f"?student_id={student.id}&semester=all&invoice_status=all"
    )
    selenium_driver.get(invoice_url)
    checkbox = selenium_driver.find_element(
        By.CSS_SELECTOR,
        f"input[name='invoice_ids'][value='{invoice.id}']",
    )
    selenium_driver.execute_script(
        """
        arguments[0].checked = true;
        arguments[0].dispatchEvent(new Event("change", { bubbles: true }));
        """,
        checkbox,
    )
    selenium_driver.find_element(By.ID, "invoice-selection-submit").click()

    def _payment_created(_driver) -> bool:
        return Payment.objects.filter(
            student_semester_invoice=invoice.student_semester_invoice
        ).exists()

    WebDriverWait(selenium_driver, 10).until(_payment_created)
    payment = Payment.objects.get(
        student_semester_invoice=invoice.student_semester_invoice
    )

    payment_url = (
        f"{live_server.url}{reverse('finance_officer_invoices')}"
        f"?tab=payments&student_id={student.id}&semester=all&payment_status=all"
    )
    selenium_driver.get(payment_url)
    _set_form_value(
        selenium_driver,
        selenium_driver.find_element(By.NAME, f"amount_paid_{payment.id}"),
        "25.00",
    )
    _set_form_value(
        selenium_driver,
        selenium_driver.find_element(By.NAME, f"payer_{payment.id}"),
        "student",
    )
    _set_form_value(
        selenium_driver,
        selenium_driver.find_element(By.NAME, f"status_{payment.id}"),
        "cleared",
    )
    _set_form_value(
        selenium_driver,
        selenium_driver.find_element(By.NAME, f"method_{payment.id}"),
        "cash",
    )
    payment_form = selenium_driver.find_element(
        By.ID,
        f"payment-update-form-{student.id}",
    )
    selenium_driver.execute_script("arguments[0].submit();", payment_form)

    def _payment_updated(_driver) -> bool:
        payment.refresh_from_db()
        return payment.status_id == "cleared" and payment.amount_paid == Decimal("25.00")

    WebDriverWait(selenium_driver, 10).until(_payment_updated)
    payment.refresh_from_db()
    assert payment.payment_method_id == "cash"
    assert payment.payer_id == "student"


def test_enrollment_can_mutate_student_profile_in_browser(
    live_server,
    selenium_driver,
    portal_user_factory,
    curriculum,
    sem_factory,
) -> None:
    """Enrollment staff can create and update a student through portal forms."""
    semester = sem_factory(1, datetime(2026, 1, 1))
    enrollment_user = portal_user_factory(
        "selenium_enrollment_mutation",
        groups=["Enrollment"],
    )
    enrollment_user.user_permissions.add(_perm("add_student"), _perm("view_student"))

    _login_fresh(selenium_driver, live_server, enrollment_user.username)
    create_url = f"{live_server.url}{reverse('create_std')}"
    selenium_driver.get(create_url)
    _clear_and_type(selenium_driver.find_element(By.ID, "id_student_id"), "SEL1001")
    _clear_and_type(selenium_driver.find_element(By.ID, "id_first_name"), "Selenium")
    _clear_and_type(selenium_driver.find_element(By.ID, "id_last_name"), "Student")
    _clear_and_type(
        selenium_driver.find_element(By.ID, "id_email"),
        "selenium.student@example.test",
    )
    Select(selenium_driver.find_element(By.ID, "id_primary_curriculum")).select_by_value(
        str(curriculum.id)
    )
    Select(selenium_driver.find_element(By.ID, "id_entry_semester")).select_by_value(
        str(semester.id)
    )
    Select(
        selenium_driver.find_element(By.ID, "id_last_enrolled_semester")
    ).select_by_value(str(semester.id))
    selenium_driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

    WebDriverWait(selenium_driver, 10).until(
        lambda _driver: Student.objects.filter(student_id="SEL1001").exists()
    )
    student = Student.objects.get(student_id="SEL1001")
    assert student.long_name == "Selenium Student"

    selenium_driver.get(f"{create_url}?student_id=SEL1001")
    _clear_and_type(selenium_driver.find_element(By.ID, "id_last_name"), "Updated")
    _clear_and_type(
        selenium_driver.find_element(By.ID, "id_email"),
        "selenium.updated@example.test",
    )
    selenium_driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

    def _student_updated(_driver) -> bool:
        student.refresh_from_db()
        student.user.refresh_from_db()
        return (
            student.long_name == "Selenium Updated"
            and student.user.email == "selenium.updated@example.test"
        )

    WebDriverWait(selenium_driver, 10).until(_student_updated)
