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
from app.finance.models.invoice import Invoice
from app.finance.models.payment import Payment
from app.timetable.models.semester import Semester
from app.timetable.utils import format_datetime

from .student_helpers import (
    _build_sidebar_links,
    _build_student_profile,
    _require_student,
)


class ReceiptRowT(TypedDict):
    """Row details for a receipt line item."""

    invoice: Invoice
    paid_total: Decimal
    paid_on: str


PaymentUpdateMapT: TypeAlias = dict[int, datetime]


@login_required
def student_payment_receipt(
    request: HttpRequest,
    semester_id: int,
) -> HttpResponse:
    """Render a payment receipt for the requested semester."""
    student = _require_student(request.user)
    semester = (
        Semester.objects.filter(pk=semester_id).select_related("academic_year").first()
    )
    if semester is None:
        raise Http404("Semester not found.")

    payments = (
        Payment.objects.filter(
            invoice__student=student,
            invoice__semester=semester,
            amount_paid__gt=0,
        )
        .select_related(
            "invoice__curriculum_course__course",
            "invoice__curriculum_course__credit_hours",
            "invoice__semester__academic_year",
        )
        .order_by("invoice__curriculum_course__course__short_code")
    )

    receipt_rows: list[ReceiptRowT] = []
    total_paid = Decimal("0.00")
    invoice_totals: dict[int, Decimal] = {}
    invoice_lookup: dict[int, Invoice] = {}
    invoice_ids: list[int] = []
    for payment in payments:
        invoice = payment.invoice
        if invoice.id not in invoice_lookup:
            invoice_lookup[invoice.id] = invoice
            invoice_ids.append(invoice.id)
        invoice_totals[invoice.id] = invoice_totals.get(invoice.id, Decimal("0.00")) + (
            payment.amount_paid
        )
    payment_last_updates: PaymentUpdateMapT = {}
    if invoice_ids:
        payment_history_rows = (
            Payment.history.filter(invoice_id__in=invoice_ids)
            .values("invoice_id")
            .annotate(last_change=Max("history_date"))
        )
        payment_last_updates = {
            row["invoice_id"]: row["last_change"]
            for row in payment_history_rows
            if row["last_change"]
        }

    for invoice_id in invoice_ids:
        invoice = invoice_lookup[invoice_id]
        paid_total = invoice_totals.get(invoice_id, Decimal("0.00"))
        paid_on = (
            format_datetime(payment_last_updates[invoice_id])
            if invoice_id in payment_last_updates
            else "-"
        )
        receipt_rows.append(
            {
                "invoice": invoice,
                "paid_total": paid_total,
                "paid_on": paid_on,
            }
        )
        total_paid += paid_total

    currency = getattr(settings, "FINANCE_DEFAULT_CURRENCY", "USD")
    semester_label = f"{semester.academic_year.code} · Semester {semester.number}"
    generated_at = format_datetime(timezone.now())

    context = {
        "student": student,
        "receipt_rows": receipt_rows,
        "currency": currency,
        "total_paid": total_paid,
        "semester_label": semester_label,
        "generated_at": generated_at,
        "student_profile": _build_student_profile(student),
        "sidebar_links": _build_sidebar_links(
            "Download payment statement",
            student=student,
        ),
    }
    return render(request, "website/student_payment_receipt.html", context)
