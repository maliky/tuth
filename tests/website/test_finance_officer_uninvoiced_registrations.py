"""Finance officer coverage for imported registrations missing invoices."""

from __future__ import annotations

from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth.models import Group, User
from django.core.paginator import Paginator as DjangoPaginator
from django.urls import reverse

from app.academics.models.department import Department
from app.finance.models.fee_stack import CrsFeeStack
from app.finance.models.invoice import CrsInvoice
from app.finance.models.payment import Payment
from app.finance.models.status_types_methods import (
    InvoiceStatus,
    Payer,
    PaymentMethod,
    PaymentStatus,
)
from app.finance.registration_invoices import ensure_course_invoice_for_registration
from app.registry.models.credit_hours import CreditHour
from app.registry.models.registration import Registration
from app.website.services import finance_portal

pytestmark = pytest.mark.django_db


def _finance_user() -> User:
    """Create a user with finance officer portal access."""
    user = User.objects.create_user(
        "finance_uninvoiced",
        password="PassW0rd!",
        is_staff=True,
    )
    group, _ = Group.objects.get_or_create(name="Finance Officer")
    user.groups.add(group)
    return user


def _zero_fee_registration(registration: Registration) -> Registration:
    """Turn a registration into the EED301 zero-credit minimum-billing case."""
    curriculum_course = registration.section.curriculum_course
    course = curriculum_course.course
    course.department = Department.get_dft("EED")
    course.number = "301"
    course.title = "Enterpreneurship Education-I"
    course.code = ""
    course.short_code = ""
    course.save()
    curriculum_course.credit_hours = CreditHour.objects.get(code=0)
    curriculum_course.save(update_fields=["credit_hours"])
    registration.refresh_from_db()
    return registration


def test_finance_officer_sees_uninvoiced_registration_actions(
    client,
    regio_factory,
) -> None:
    """Imported pending registrations should not disappear from finance UI."""
    registration = regio_factory("finance_uninvoiced_student", "CURRI_FIN_UI", "803", 1)
    client.force_login(_finance_user())

    response = client.get(
        reverse("finance_officer_invoices"),
        {"student_id": str(registration.student.id)},
    )

    assert response.status_code == 200
    assert b'option value="all" selected' in response.content
    assert b"Uninvoiced registrations" in response.content
    assert b"Generate missing invoices" in response.content
    assert (
        registration.section.curriculum_course.course.short_code.encode()
        in response.content
    )


def test_finance_officer_can_generate_missing_registration_invoices(
    client,
    regio_factory,
) -> None:
    """Finance staff should materialize invoice rows before creating payments."""
    registration = regio_factory("finance_generate_student", "CURRI_FIN_GEN", "804", 1)
    client.force_login(_finance_user())

    response = client.post(
        reverse("finance_officer_generate_registration_invoices"),
        {
            "student_id": str(registration.student.id),
            "registration_ids": [str(registration.id)],
            "next": reverse("finance_officer_invoices"),
        },
        follow=True,
    )

    assert response.status_code == 200
    invoice = CrsInvoice.objects.get(student=registration.student)
    assert invoice.curriculum_course == registration.section.curriculum_course
    assert invoice.semester == registration.section.semester
    assert invoice.balance == registration.section.fee_total_amount()


def test_finance_autocomplete_includes_students_with_missing_invoices(
    client,
    regio_factory,
) -> None:
    """Finance student search should include registration-only debt."""
    registration = regio_factory(
        "finance_autocomplete_student",
        "CURRI_FIN_AUTO",
        "805",
        1,
    )
    client.force_login(_finance_user())

    response = client.get(
        reverse("finance_officer_std_autocomplete"),
        {"q": registration.student.student_id},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["id"] == registration.student.id


def test_finance_officer_sees_zero_credit_registrations_as_billable(
    client,
    regio_factory,
) -> None:
    """Zero-credit pending courses should be billable without manual fee setup."""
    registration = _zero_fee_registration(
        regio_factory("finance_fee_setup_student", "CURRI_FIN_FEE", "301", 1)
    )
    client.force_login(_finance_user())

    response = client.get(
        reverse("finance_officer_invoices"),
        {"student_id": str(registration.student.id)},
    )

    assert response.status_code == 200
    assert b"Uninvoiced registrations" in response.content
    assert b"EED301" in response.content
    assert b"Generate missing invoices" in response.content
    assert b"Needs fee setup" not in response.content


def test_finance_officer_sees_stale_zero_invoice_as_billable_generation(
    client,
    regio_factory,
) -> None:
    """Existing zero invoices should expose normal generation/update action."""
    registration = _zero_fee_registration(
        regio_factory("finance_stale_zero_student", "CURRI_FIN_STALE", "301", 1)
    )
    CrsInvoice.objects.create(
        student=registration.student,
        curriculum_course=registration.section.curriculum_course,
        semester=registration.section.semester,
        initial_amount_due=Decimal("0.00"),
        balance=Decimal("0.00"),
    )
    client.force_login(_finance_user())

    response = client.get(
        reverse("finance_officer_invoices"),
        {"student_id": str(registration.student.id)},
    )

    assert response.status_code == 200
    assert b"Uninvoiced registrations" in response.content
    assert b"EED301" in response.content
    assert b"Generate missing invoices" in response.content


def test_finance_officer_uninvoiced_registration_pagination_is_visible(
    client,
    monkeypatch,
    regio_factory,
    sec_factory,
) -> None:
    """Registration panels should expose their own pagination controls."""

    class TinyPaginator(DjangoPaginator):
        """Force pagination in a compact fixture."""

        def __init__(self, object_list, per_page, *args, **kwargs):
            super().__init__(object_list, 1, *args, **kwargs)

    first_registration = regio_factory(
        "finance_registration_pages_student",
        "CURRI_FIN_PAGES",
        "811",
        1,
    )
    second_section = sec_factory("812", "CURRI_FIN_PAGES", 1, 1)
    Registration.objects.create(
        student=first_registration.student,
        section=second_section,
    )
    monkeypatch.setattr(finance_portal, "Paginator", TinyPaginator)
    client.force_login(_finance_user())

    response = client.get(
        reverse("finance_officer_invoices"),
        {"student_id": str(first_registration.student.id)},
    )

    assert response.status_code == 200
    assert b'name="registration_page"' in response.content
    assert b"registration_page=2" in response.content


def test_finance_officer_can_set_total_fee_and_generate_invoice(
    client,
    regio_factory,
) -> None:
    """Finance staff should create the invoice when the policy already gives amount."""
    registration = _zero_fee_registration(
        regio_factory("finance_set_fee_student", "CURRI_FIN_SET", "301", 1)
    )
    client.force_login(_finance_user())

    response = client.post(
        reverse("finance_officer_setup_registration_fee"),
        {
            "registration_id": str(registration.id),
            "fee_type_code": "entrepreneurship_education_i",
            "amount": "15.00",
            "clear_now": "0",
            "next": reverse("finance_officer_invoices"),
        },
        follow=True,
    )

    assert response.status_code == 200
    invoice = CrsInvoice.objects.get(student=registration.student)
    assert invoice.initial_amount_due == Decimal("15.00")
    assert invoice.balance == Decimal("15.00")
    assert not CrsFeeStack.objects.filter(
        course=registration.section.curriculum_course.course
    ).exists()


def test_finance_officer_can_set_fee_and_clear_registration(
    client,
    regio_factory,
) -> None:
    """Finance staff should be able to clear a setup-fee course directly."""
    registration = _zero_fee_registration(
        regio_factory("finance_clear_fee_student", "CURRI_FIN_CLEAR", "301", 1)
    )
    client.force_login(_finance_user())

    response = client.post(
        reverse("finance_officer_setup_registration_fee"),
        {
            "registration_id": str(registration.id),
            "fee_type_code": "entrepreneurship_education_i",
            "amount": "15.00",
            "clear_now": "1",
            "next": reverse("finance_officer_invoices"),
        },
        follow=True,
    )

    assert response.status_code == 200
    invoice = CrsInvoice.objects.get(student=registration.student)
    invoice.refresh_from_db()
    assert invoice.balance == Decimal("0.00")
    payment = Payment.objects.get(
        student_semester_invoice=invoice.student_semester_invoice
    )
    assert payment.amount_paid == Decimal("15.00")
    assert payment.status_id == "cleared"
    registration.refresh_from_db()
    assert registration.status_id == "cleared"


def test_finance_officer_clears_only_selected_fee_setup_registration(
    client,
    regio_factory,
    sec_factory,
) -> None:
    """Set fee + clear should not clear sibling charges in the same semester."""
    registration = _zero_fee_registration(
        regio_factory("finance_clear_one_student", "CURRI_FIN_CLEAR_ONE", "301", 1)
    )
    sibling_section = sec_factory("813", "CURRI_FIN_CLEAR_ONE", 1, 1)
    sibling_registration = Registration.objects.create(
        student=registration.student,
        section=sibling_section,
    )
    sibling_invoice, _, _ = ensure_course_invoice_for_registration(sibling_registration)
    assert sibling_invoice is not None
    sibling_balance = sibling_invoice.balance
    client.force_login(_finance_user())

    response = client.post(
        reverse("finance_officer_setup_registration_fee"),
        {
            "registration_id": str(registration.id),
            "fee_type_code": "entrepreneurship_education_i",
            "amount": "15.00",
            "clear_now": "1",
            "next": reverse("finance_officer_invoices"),
        },
        follow=True,
    )

    assert response.status_code == 200
    target_invoice = CrsInvoice.objects.get(
        student=registration.student,
        curriculum_course=registration.section.curriculum_course,
    )
    target_invoice.refresh_from_db()
    sibling_invoice.refresh_from_db()
    assert target_invoice.balance == Decimal("0.00")
    assert target_invoice.status_id == "cleared"
    assert sibling_invoice.balance == sibling_balance
    assert sibling_invoice.status_id != "cleared"
    sibling_registration.refresh_from_db()
    assert sibling_registration.status_id != "cleared"
    assert Payment.objects.get(
        student_semester_invoice=target_invoice.student_semester_invoice
    ).amount_paid == Decimal("15.00")


def test_payment_group_total_paid_excludes_pending_amounts(
    curriculum_course_factory,
    sem_factory,
    student,
) -> None:
    """Finance payment totals should separate cleared and pending money."""
    PaymentStatus._populate_attributes_and_db()
    curriculum_course = curriculum_course_factory("814", "CURRI_FIN_PAY_TOTALS")
    semester = sem_factory(1)
    invoice = CrsInvoice.objects.create(
        student=student,
        curriculum_course=curriculum_course,
        semester=semester,
        initial_amount_due=Decimal("150.00"),
        balance=Decimal("150.00"),
    )
    parent_invoice = invoice.student_semester_invoice
    assert parent_invoice is not None
    Payment.objects.create(
        student_semester_invoice=parent_invoice,
        amount_paid=Decimal("100.00"),
        status_id="cleared",
    )
    Payment.objects.create(
        student_semester_invoice=parent_invoice,
        amount_paid=Decimal("50.00"),
        status_id="pending",
    )

    groups = finance_portal.gp_payments(
        Payment.objects.filter(student_semester_invoice=parent_invoice).select_related(
            "student_semester_invoice__student",
            "status",
            "payer",
            "payment_method",
        )
    )

    assert groups[0]["total_paid"] == Decimal("100.00")
    assert groups[0]["cleared_records_total"] == Decimal("100.00")
    assert groups[0]["applied_clearance_total"] == Decimal("100.00")
    assert groups[0]["surplus_total"] == Decimal("0.00")
    assert groups[0]["open_balance"] == Decimal("50.00")
    assert groups[0]["pending_total"] == Decimal("50.00")
    assert groups[0]["pending_count"] == 1
    assert all("814" in row["course_summary"] for row in groups[0]["rows"])


def test_payment_group_surplus_separates_records_from_applied_clearance(
    curriculum_course_factory,
    sem_factory,
    student,
) -> None:
    """Finance totals should explain payment records above semester charges."""
    InvoiceStatus._populate_attributes_and_db()
    PaymentStatus._populate_attributes_and_db()
    PaymentMethod._populate_attributes_and_db()
    Payer._populate_attributes_and_db()
    curriculum_course = curriculum_course_factory("815", "CURRI_FIN_PAY_SURPLUS")
    semester = sem_factory(1)
    invoice = CrsInvoice.objects.create(
        student=student,
        curriculum_course=curriculum_course,
        semester=semester,
        initial_amount_due=Decimal("45.00"),
        balance=Decimal("45.00"),
    )
    parent_invoice = invoice.student_semester_invoice
    assert parent_invoice is not None
    Payment.objects.create(
        student_semester_invoice=parent_invoice,
        amount_paid=Decimal("100.00"),
        status_id="cleared",
    )

    groups = finance_portal.gp_payments(
        Payment.objects.filter(student_semester_invoice=parent_invoice).select_related(
            "student_semester_invoice__student",
            "status",
            "payer",
            "payment_method",
        )
    )

    group = groups[0]
    assert group["charged_total"] == Decimal("45.00")
    assert group["cleared_records_total"] == Decimal("100.00")
    assert group["total_paid"] == Decimal("100.00")
    assert group["applied_clearance_total"] == Decimal("45.00")
    assert group["surplus_total"] == Decimal("55.00")
    assert group["open_balance"] == Decimal("0.00")
    assert group["rows"][0]["charged_total"] == Decimal("45.00")
    assert group["rows"][0]["applied_clearance"] == Decimal("45.00")
    assert group["rows"][0]["surplus"] == Decimal("55.00")


def test_finance_officer_create_payments_redirects_to_payment_review(
    client,
    curriculum_course_factory,
    sem_factory,
    student,
) -> None:
    """Creating payments for one student should land on visible payment rows."""
    PaymentStatus._populate_attributes_and_db()
    curriculum_course = curriculum_course_factory("815", "CURRI_FIN_PAY_REVIEW")
    semester = sem_factory(1)
    invoice = CrsInvoice.objects.create(
        student=student,
        curriculum_course=curriculum_course,
        semester=semester,
        initial_amount_due=Decimal("90.00"),
        balance=Decimal("90.00"),
    )
    client.force_login(_finance_user())

    response = client.post(
        reverse("finance_officer_create_payments"),
        {
            "invoice_ids": [str(invoice.id)],
            "next": "/should-not-hide-the-payment-row/",
        },
    )

    assert response.status_code == 302
    location = response.headers["Location"]
    parsed = urlparse(location)
    params = parse_qs(parsed.query)
    assert parsed.path == reverse("finance_officer_invoices")
    assert params["tab"] == ["payments"]
    assert params["payment_status"] == ["all"]
    assert params["semester"] == ["all"]
    assert params["student_id"] == [str(student.id)]
    payment = Payment.objects.get(
        student_semester_invoice=invoice.student_semester_invoice
    )
    assert payment.status_id == "pending"
    assert payment.amount_paid == Decimal("90.00")

    page_response = client.get(location)
    assert page_response.status_code == 200
    assert b"Save payment changes" in page_response.content
    assert b"data-payment-edit-field" in page_response.content
    assert b'<tr class="table-warning" title=' not in page_response.content
    assert b'title="Created:' in page_response.content
    assert b"course invoice" in page_response.content
    assert b"815" in page_response.content
