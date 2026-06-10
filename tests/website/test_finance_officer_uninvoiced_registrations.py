"""Finance officer coverage for imported registrations missing invoices."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from django.core.paginator import Paginator as DjangoPaginator
from django.urls import reverse

from app.academics.models.department import Department
from app.finance.models.fee_stack import CrsFeeStack, FeeStackLine
from app.finance.models.invoice import CrsInvoice
from app.finance.models.payment import Payment
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
    """Turn a registration into the EED301 zero-credit fee-setup case."""
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


def test_finance_officer_sees_zero_amount_registrations_as_fee_setup(
    client,
    regio_factory,
) -> None:
    """Zero-credit pending courses should show as actionable fee setup rows."""
    registration = _zero_fee_registration(
        regio_factory("finance_fee_setup_student", "CURRI_FIN_FEE", "301", 1)
    )
    client.force_login(_finance_user())

    response = client.get(
        reverse("finance_officer_invoices"),
        {"student_id": str(registration.student.id)},
    )

    assert response.status_code == 200
    assert b"Needs fee setup" in response.content
    assert b"EED301" in response.content
    assert b"Set fee + clear" in response.content


def test_finance_officer_sees_stale_zero_invoice_as_fee_setup(
    client,
    regio_factory,
) -> None:
    """Existing zero invoices should still expose the fee setup action."""
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
    assert b"Needs fee setup" in response.content
    assert b"EED301" in response.content
    assert b"Set fee + clear" in response.content


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


def test_finance_officer_can_set_fee_and_generate_invoice(
    client,
    regio_factory,
) -> None:
    """Finance staff should attach a course fee and create the missing invoice."""
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
    assert CrsFeeStack.objects.filter(
        course=registration.section.curriculum_course.course
    ).exists()
    assert FeeStackLine.objects.filter(amount=Decimal("15.00")).exists()


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
