"""Student payment receipt views."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TypeAlias, TypedDict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from app.finance.models.invoice import CrsInvoice, StdSemesterInvoice
from app.finance.models.payment import Payment
from app.finance.payment_application import payment_application_for_parent_invoice
from app.timetable.models.semester import Semester
from app.timetable.utils import format_datetime

from .student_helpers import (
    _build_sidebar_links,
    _build_std_profile,
    _require_std,
)


class ReceiptRowT(TypedDict):
    """Row details for a receipt line item."""

    invoice: CrsInvoice
    paid_total: Decimal
    paid_on: str


PaymentUpdateMapT: TypeAlias = dict[int, datetime]


@login_required
def std_payment_receipt(
    request: HttpRequest,
    semester_id: int,
) -> HttpResponse:
    """Render a payment receipt for the requested semester."""
    student = _require_std(request.user)
    semester = (
        Semester.objects.filter(pk=semester_id).select_related("academic_year").first()
    )
    if semester is None:
        raise Http404("Semester not found.")

    parent_invoice = (
        StdSemesterInvoice.objects.filter(student=student, semester=semester)
        .select_related("student", "semester__academic_year")
        .first()
    )
    payments: list[Payment] = []
    invoices: list[CrsInvoice] = []
    if parent_invoice is not None:
        payments = list(
            Payment.objects.filter(
                student_semester_invoice=parent_invoice,
                amount_paid__gt=0,
                status_id="cleared",
            ).order_by("id")
        )
        invoices = list(
            parent_invoice.course_invoices.select_related(
                "curriculum_course__course",
                "curriculum_course__credit_hours",
                "semester__academic_year",
            ).order_by("curriculum_course__course__short_code")
        )

    receipt_rows: list[ReceiptRowT] = []
    total_recorded = Decimal("0.00")
    total_applied = Decimal("0.00")
    surplus = Decimal("0.00")
    payment_last_updates: PaymentUpdateMapT = {}
    if parent_invoice is not None and payments:
        application = payment_application_for_parent_invoice(parent_invoice, payments)
        total_recorded = application["cleared_records_total"]
        total_applied = application["applied_clearance"]
        surplus = application["surplus"]
        payment_history = Payment.history.filter(
            student_semester_invoice_id=parent_invoice.id
        ).aggregate(last_change=Max("history_date"))
        if payment_history.get("last_change"):
            payment_last_updates[parent_invoice.id] = payment_history["last_change"]
        paid_on_label = (
            format_datetime(payment_last_updates[parent_invoice.id])
            if parent_invoice.id in payment_last_updates
            else format_datetime(parent_invoice.updated_at or parent_invoice.created_at)
        )

        remaining_paid = total_applied
        for invoice in invoices:
            applied_paid = min(invoice.initial_amount_due, remaining_paid)
            remaining_paid -= applied_paid
            amount_due = invoice.initial_amount_due - applied_paid
            # Template expects an amount_due attribute on each invoice row.
            invoice.amount_due = amount_due  # type: ignore[attr-defined]
            receipt_rows.append(
                {
                    "invoice": invoice,
                    "paid_total": applied_paid,
                    "paid_on": paid_on_label,
                }
            )

    currency = getattr(settings, "FINANCE_DEFAULT_CURRENCY", "USD")
    sem_label = f"{semester.academic_year.code} · Semester {semester.number}"
    generated_at = format_datetime(timezone.now())

    context = {
        "student": student,
        "receipt_rows": receipt_rows,
        "currency": currency,
        "total_paid": total_applied,
        "total_applied": total_applied,
        "total_recorded": total_recorded,
        "surplus": surplus,
        "semester_label": sem_label,
        "generated_at": generated_at,
        "student_profile": _build_std_profile(student),
        "sidebar_links": _build_sidebar_links(
            "Download payment statement",
            student=student,
        ),
    }
    return render(request, "website/student_payment_receipt.html", context)
