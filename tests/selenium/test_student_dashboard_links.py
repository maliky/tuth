"""Behavioral tests for student dashboard sidebar navigation."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.academics.models.curriculum import Curriculum
from app.people.models.student import Student
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester
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


def _create_student_user(username: str, semester: Semester):
    """Create a student user linked to the supplied semester."""
    UserModel = get_user_model()
    user = UserModel.objects.create_user(username=username)
    user.set_password(TEST_PASSWORD)
    user.save()
    Student.objects.create(
        user=user,
        curriculum=Curriculum.get_default(),
        entry_semester=semester,
        last_enrolled_semester=semester,
    )
    return user


def test_student_dashboard_sidebar_links_route_to_statements(
    live_server,
    selenium_driver,
):
    """Sidebar links should route to payment and invoice statement pages."""
    today = timezone.now().date()
    academic_year = AcademicYear.get_default(today)
    semester = Semester.objects.create(
        academic_year=academic_year,
        number=1,
        start_date=today - timedelta(days=1),
    )
    user = _create_student_user("student_links", semester)

    _login_to_portal(selenium_driver, live_server, user.username)

    dashboard_url = f"{live_server.url}{reverse('student_dashboard')}"
    selenium_driver.get(dashboard_url)

    invoice_path = reverse("student_invoice_statement")
    payment_path = reverse("student_payment_receipt", args=[semester.id])

    invoice_link = selenium_driver.find_element(
        By.CSS_SELECTOR, f".portal-nav a[href$='{invoice_path}']"
    )
    payment_link = selenium_driver.find_element(
        By.CSS_SELECTOR, f".portal-nav a[href$='{payment_path}']"
    )

    invoice_link.click()
    WebDriverWait(selenium_driver, 10).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "h1"), "Invoice Statement")
    )

    selenium_driver.get(payment_link.get_attribute("href"))
    WebDriverWait(selenium_driver, 10).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "h1"), "Payment Receipt")
    )
