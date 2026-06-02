"""Regression tests for P0 findings from the Django admin click audit."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from app.academics.models.student_curriculum_enrollment import CurriStdEnroll
from app.finance.models.invoice import CrsInvoice
from app.finance.models.status_types_methods import InvoiceStatus, Payer
from app.registry.models.status_types import TranscriptRequestStatus

pytestmark = pytest.mark.django_db


def _login_admin(client, superuser) -> None:
    """Authenticate the test client as a superuser."""
    client.force_login(superuser)


def _assert_ok(response) -> None:
    """Assert that an admin GET rendered successfully."""
    assert response.status_code == 200, response.content[:500]


def test_department_admin_search_and_role_assignment_autocomplete_load(
    client,
    superuser,
    department,
) -> None:
    """Department search must not break direct or dependent admin autocomplete."""
    _login_admin(client, superuser)

    department_response = client.get(
        reverse("admin:academics_department_changelist"),
        {"q": department.college.code},
    )
    _assert_ok(department_response)

    autocomplete_response = client.get(
        reverse("admin:autocomplete"),
        {
            "app_label": "people",
            "model_name": "roleassignment",
            "field_name": "department",
            "term": department.code,
        },
    )
    _assert_ok(autocomplete_response)


def test_transcript_request_admin_search_loads(client, superuser, student) -> None:
    """Transcript request search must use concrete related text fields."""
    _login_admin(client, superuser)
    TranscriptRequestStatus._populate_attributes_and_db()

    response = client.get(
        reverse("admin:registry_transcriptrequest_changelist"),
        {"q": student.student_id or student.long_name},
    )
    _assert_ok(response)


def test_finance_invoice_facets_load(
    client,
    superuser,
    registration,
) -> None:
    """Invoice facet links must not conflict with admin query optimizations."""
    _login_admin(client, superuser)
    InvoiceStatus._populate_attributes_and_db()
    Payer._populate_attributes_and_db()
    course_invoice = CrsInvoice.objects.create(
        curriculum_course=registration.section.curriculum_course,
        student=registration.student,
        semester=registration.section.semester,
        initial_amount_due=Decimal("100.00"),
        balance=Decimal("100.00"),
    )
    parent_invoice = course_invoice.student_semester_invoice
    assert parent_invoice is not None

    course_response = client.get(
        reverse("admin:finance_crsinvoice_changelist"),
        {"_facets": "True", "q": course_invoice.student.student_id},
    )
    _assert_ok(course_response)

    parent_response = client.get(
        reverse("admin:finance_stdsemesterinvoice_changelist"),
        {"_facets": "True", "q": parent_invoice.student.student_id},
    )
    _assert_ok(parent_response)


def test_non_history_admin_history_views_load(
    client, superuser, faculty, student
) -> None:
    """Admins without simple-history managers should use Django's stock history."""
    _login_admin(client, superuser)
    enrollment = CurriStdEnroll.objects.get(
        pk=student.curriculum_enrollments.values_list("pk", flat=True).first()
    )

    faculty_response = client.get(
        reverse("admin:people_faculty_history", args=[faculty.pk])
    )
    _assert_ok(faculty_response)

    enrollment_response = client.get(
        reverse("admin:academics_curristdenroll_history", args=[enrollment.pk])
    )
    _assert_ok(enrollment_response)
