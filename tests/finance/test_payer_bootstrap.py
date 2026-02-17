"""Tests for runtime payer lookup bootstrap in invoice writes."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.finance.models.invoice import CrsInvoice
from app.finance.models.status_types_methods import Payer

pytestmark = pytest.mark.django_db


def test_crs_invoice_creation_bootstraps_all_payers(regio_factory) -> None:
    """Creating a course invoice should recreate all payer lookup defaults."""
    Payer.objects.all().delete()
    assert Payer.objects.count() == 0

    reg = regio_factory("payer_bootstrap_student", "CURRI_TEST", "101", 1)
    amount = Decimal("10.00")
    invoice = CrsInvoice.objects.create(
        curriculum_course=reg.section.curriculum_course,
        student=reg.student,
        semester=reg.section.semester,
        initial_amount_due=amount,
        balance=amount,
    )
    parent_invoice = invoice.student_semester_invoice
    assert parent_invoice is not None
    parent_invoice.refresh_from_db()

    payer_codes = set(Payer.objects.values_list("code", flat=True))
    expected_codes = {code for code, _label in Payer.DEFAULT_VALUES}
    assert expected_codes.issubset(payer_codes)
    assert parent_invoice.course_tuition_payer_id == "gov"
    assert parent_invoice.fee_payer_id == "student"
