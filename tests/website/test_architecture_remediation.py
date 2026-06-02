"""Regression coverage for architecture-audit remediation work."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, Permission, User
from django.urls import reverse

from app.academics.models.college import College
from app.academics.models.curriculum import Curriculum
from app.finance.models.payment import Payment
from app.finance.models.status_types_methods import (
    InvoiceStatus,
    Payer,
    PaymentMethod,
    PaymentStatus,
)
from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.shared.models import ApprovalQueue
from tests.constants import D100

pytestmark = pytest.mark.django_db
pytest_plugins = ["tests.finance.fixture"]


def _group_user(user: User, group_name: str) -> None:
    """Attach a user to a role group."""
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)


def _ensure_finance_defaults() -> None:
    """Create lookup rows required by finance portal mutations."""
    InvoiceStatus._populate_attributes_and_db()
    PaymentStatus._populate_attributes_and_db()
    PaymentMethod._populate_attributes_and_db()
    Payer._populate_attributes_and_db()


def _perm(codename: str) -> Permission:
    """Return a permission by codename for concise test setup."""
    return Permission.objects.get(codename=codename)


def test_dean_can_request_curriculum_activation(client) -> None:
    """Dean curriculum review should create one VPAA activation request."""
    college = College.objects.create(code="TDEAN", long_name="Dean Test College")
    curriculum = Curriculum.objects.create(
        short_name="BSC-DEAN",
        long_name="Dean Review Curriculum",
        college=college,
        status_id="pending",
    )
    user = User.objects.create_user(
        username="dean_arch",
        first_name="Dean",
        last_name="Tester",
        password="PassW0rd!",
    )
    _group_user(user, "Dean")
    staff = Staff(user=user, position="Dean")
    staff.save()
    faculty = Faculty(staff_profile=staff, college=college)
    faculty.save()

    client.force_login(user)
    list_response = client.get(reverse("dean_curricula"))
    assert list_response.status_code == 200
    assert b"Dean Review Curriculum" in list_response.content

    detail_response = client.get(reverse("dean_curriculum_detail", args=[curriculum.id]))
    assert detail_response.status_code == 200
    assert (
        reverse("dean_curriculum_request_activation", args=[curriculum.id]).encode()
        in detail_response.content
    )

    post_response = client.post(
        reverse("dean_curriculum_request_activation", args=[curriculum.id]),
        follow=True,
    )
    assert post_response.status_code == 200
    approvals = ApprovalQueue.objects.filter(
        request_type="curriculum_activation",
        target_role="vpaa",
        related_object_id=curriculum.id,
    )
    assert approvals.count() == 1

    second_response = client.post(
        reverse("dean_curriculum_request_activation", args=[curriculum.id]),
        follow=True,
    )
    assert second_response.status_code == 200
    assert approvals.count() == 1


def test_finance_officer_can_create_and_update_payments(
    client,
    regio_factory,
    invoice_factory,
) -> None:
    """Finance payment POSTs should work with disposable test data."""
    _ensure_finance_defaults()
    user = User.objects.create_user("finance_arch", password="PassW0rd!")
    _group_user(user, "Finance Officer")
    registration = regio_factory("finance_arch_student", "CURR_FIN_ARCH", "701", 1)
    invoice = invoice_factory(registration, D100)

    client.force_login(user)
    create_response = client.post(
        reverse("finance_officer_create_payments"),
        {"invoice_ids": [str(invoice.id)]},
    )
    assert create_response.status_code == 302
    payment = Payment.objects.get(
        student_semester_invoice=invoice.student_semester_invoice
    )
    assert payment.amount_paid == D100
    assert payment.status_id == "pending"

    update_response = client.post(
        reverse("finance_officer_update_payments"),
        {
            "payment_ids": [str(payment.id)],
            f"amount_paid_{payment.id}": "25.00",
            f"status_{payment.id}": "cleared",
            f"method_{payment.id}": "cash",
            f"payer_{payment.id}": "student",
        },
    )
    assert update_response.status_code == 302
    payment.refresh_from_db()
    assert payment.amount_paid == Decimal("25.00")
    assert payment.status_id == "cleared"
    assert payment.payment_method_id == "cash"
    assert payment.payer_id == "student"


def test_enrollment_can_create_and_update_student_in_portal(
    client,
    curriculum,
    sem_factory,
) -> None:
    """Enrollment create/update should stay inside portal-native forms."""
    semester = sem_factory(1, datetime(2026, 1, 1))
    user = User.objects.create_user("enrollment_arch", password="PassW0rd!")
    _group_user(user, "Enrollment")
    user.user_permissions.add(_perm("add_student"), _perm("view_student"))
    client.force_login(user)

    create_response = client.post(
        reverse("create_std"),
        {
            "student_id": "ARCH1001",
            "first_name": "Portal",
            "last_name": "Student",
            "email": "portal.student@example.test",
            "primary_curriculum": str(curriculum.id),
            "entry_semester": str(semester.id),
            "last_enrolled_semester": str(semester.id),
        },
    )
    assert create_response.status_code == 302
    student = Student.objects.get(student_id="ARCH1001")
    assert student.long_name == "Portal Student"

    update_response = client.post(
        f"{reverse('create_std')}?student_id=ARCH1001",
        {
            "student_id": "ARCH1001",
            "first_name": "Portal",
            "last_name": "Updated",
            "email": "portal.updated@example.test",
            "primary_curriculum": str(curriculum.id),
            "entry_semester": str(semester.id),
            "last_enrolled_semester": str(semester.id),
        },
    )
    assert update_response.status_code == 302
    student.refresh_from_db()
    student.user.refresh_from_db()
    assert student.long_name == "Portal Updated"
    assert student.user.email == "portal.updated@example.test"


def test_staff_sidebar_exposes_dean_curriculum_task(client) -> None:
    """Dean dashboard should expose curriculum review as a task-oriented action."""
    user = User.objects.create_user("dean_sidebar_arch", password="PassW0rd!")
    _group_user(user, "Dean")
    client.force_login(user)

    response = client.get(reverse("staff_role_dashboard", args=["dean"]))
    assert response.status_code == 200
    assert b"Curriculum review" in response.content
    assert reverse("dean_curricula").encode() in response.content
