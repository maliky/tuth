"""Student payment receipt views."""

from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from app.finance.models.invoice import Invoice
from app.timetable.models.semester import Semester

from .student_helpers import (
    _build_sidebar_links,
    _build_student_profile,
    _require_student,
)


class ReceiptRowT(TypedDict):
    """Row details for a receipt line item."""

    invoice: Invoice
    paid_total: Decimal


@login_required
def student_payment_receipt(
    request: HttpRequest,
    semester_id: int,
) -> HttpResponse:
    """Render a cleared payment receipt for the requested semester."""
    student = _require_student(request.user)
    semester = (
        Semester.objects.filter(pk=semester_id).select_related("academic_year").first()
    )
    if semester is None:
        raise Http404("Semester not found.")

    invoices = list(
        Invoice.objects.filter(
            student=student,
            semester=semester,
            amount_due__lte=0,
        )
        .select_related(
            "curriculum_course__course",
            "curriculum_course__credit_hours",
            "semester__academic_year",
        )
        .prefetch_related("payments__status", "payments__payment_method")
        .order_by("curriculum_course__course__short_code")
    )

    receipt_rows: list[ReceiptRowT] = []
    total_paid = Decimal("0.00")
    for invoice in invoices:
        paid_total = sum(
            (
                payment.amount_paid
                for payment in invoice.payments.all()
                if payment.status_id == "cleared"
            ),
            Decimal("0.00"),
        )
        receipt_rows.append({"invoice": invoice, "paid_total": paid_total})
        total_paid += paid_total

    currency = getattr(settings, "FINANCE_DEFAULT_CURRENCY", "USD")
    semester_label = f"{semester.academic_year.code} · Semester {semester.number}"

    context = {
        "student": student,
        "receipt_rows": receipt_rows,
        "currency": currency,
        "total_paid": total_paid,
        "semester_label": semester_label,
        "student_profile": _build_student_profile(student),
        "sidebar_links": _build_sidebar_links("Financials"),
    }
    return render(request, "website/student_payment_receipt.html", context)
