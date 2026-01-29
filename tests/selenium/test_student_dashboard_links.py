"""Behavioral tests for student dashboard sidebar navigation."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.academics.models.curriculum_course import CurriculumCourse
from app.finance.models.invoice import Invoice
from app.finance.models.payment import Payment
from app.academics.models.curriculum import Curriculum
from app.people.models.student import Student
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester
from tests.selenium.test_portal_roles import TEST_PASSWORD, _login_to_portal

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.selenium,
]


def _create_student_user(username: str, semester: Semester):
    """Create a student user linked to the supplied semester."""
    UserModel = get_user_model()
    user, _created = UserModel.objects.get_or_create(username=username)
    user.set_password(TEST_PASSWORD)
    user.save()
    Student.objects.get_or_create(
        user=user,
        defaults={
            "curriculum": Curriculum.get_default(),
            "entry_semester": semester,
            "last_enrolled_semester": semester,
        },
    )
    return user


def test_student_payment_receipt_shows_paid_on_column(
    live_server,
    selenium_driver,
):
    """Receipt table should include the date paid column."""
    today = timezone.now().date()
    academic_year = AcademicYear.get_default(today)
    semester = Semester.objects.create(
        academic_year=academic_year,
        number=1,
        start_date=today - timedelta(days=1),
    )
    user = _create_student_user("student_receipt", semester)
    student = Student.objects.get(user=user)
    curriculum_course = CurriculumCourse.get_default()
    invoice = Invoice.objects.create(
        curriculum_course=curriculum_course,
        student=student,
        semester=semester,
        initial_amount_due=Decimal("100.00"),
        balance=Decimal("100.00"),
    )
    Payment.objects.create(
        invoice=invoice,
        amount_paid=Decimal("25.00"),
    )

    _login_to_portal(selenium_driver, live_server, user.username)
    receipt_path = reverse("student_payment_receipt", args=[semester.id])
    receipt_url = f"{live_server.url}{receipt_path}"
    selenium_driver.get(receipt_url)

    WebDriverWait(selenium_driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
    )
    assert "Date paid" in selenium_driver.page_source
