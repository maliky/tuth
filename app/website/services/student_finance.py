"""Student portal finance statement services."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from app.finance.models.invoice import CrsInvoice, StdSemesterInvoice
from app.timetable.utils import format_datetime
from app.website.views.student_helpers import (
    _build_sidebar_links,
    _build_std_profile,
    _require_std,
)


def download_invoice_statement_response(request: HttpRequest) -> HttpResponse:
    """Redirect to the invoice statement view."""
    _require_std(request.user)
    return redirect(reverse("std_invoice_statement"))


def std_invoice_statement_response(request: HttpRequest) -> HttpResponse:
    """Render the invoice statement for the current student."""
    student = _require_std(request.user)
    invoices = list(
        CrsInvoice.objects.filter(student=student, balance__gt=0)
        .select_related(
            "curriculum_course__course",
            "curriculum_course__credit_hours",
            "semester__academic_year",
        )
        .order_by("semester__start_date", "curriculum_course__course__short_code")
    )
    total_due = StdSemesterInvoice.objects.filter(student=student).aggregate(
        total=Sum("balance")
    ).get("total") or Decimal("0.00")
    currency = getattr(settings, "FINANCE_DEFAULT_CURRENCY", "USD")
    statement_rows = [
        {"invoice": invoice, "created_at": format_datetime(invoice.created_at)}
        for invoice in invoices
    ]
    student_profile = _build_std_profile(student)
    sidebar_links = _build_sidebar_links("Download invoice statement", student=student)
    context = {
        "student": student,
        "statement_rows": statement_rows,
        "currency": currency,
        "total_due": total_due,
        "student_profile": student_profile,
        "sidebar_links": sidebar_links,
    }
    return render(request, "website/student_invoice_statement.html", context)


__all__ = [
    "download_invoice_statement_response",
    "std_invoice_statement_response",
]
