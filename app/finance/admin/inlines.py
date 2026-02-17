"""Inline helpers for finance admin displays."""

from __future__ import annotations

from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html
from django.utils.http import urlencode

from app.finance.models.invoice import CrsInvoice
from app.finance.models.payment import Payment


class StdInvoiceIL(admin.TabularInline):
    """Inline list of student invoices with payment counts."""

    model = CrsInvoice
    fk_name = "student"
    classes = ["collapse"]
    can_delete = False
    extra = 0
    fields = (
        "semester",
        "curriculum_course",
        "balance",
        "payments_link",
        "created_at",
    )
    readonly_fields = ("payments_link", "created_at")

    def get_queryset(self, request):
        """Annotate invoice rows with payment counts."""
        qs = super().get_queryset(request)
        return qs.select_related("semester", "curriculum_course").annotate(
            payments_count=Count("student_semester_invoice__payments", distinct=True)
        )

    @admin.display(description="Payments")
    def payments_link(self, obj: CrsInvoice) -> str:
        """Return a link to filtered payments for the invoice."""
        count = getattr(obj, "payments_count", 0)
        parent_invoice_id = obj.student_semester_invoice_id
        if not count or parent_invoice_id is None:
            return "0"
        base_url = reverse("admin:finance_payment_changelist")
        query = urlencode({"student_semester_invoice__id__exact": parent_invoice_id})
        return format_html('<a href="{}?{}">{}</a>', base_url, query, count)


class StdSemInvoicePaymentIL(admin.TabularInline):
    """Inline list of payments attached to a student-semester invoice."""

    model = Payment
    fk_name = "student_semester_invoice"
    classes = ["collapse"]
    extra = 0
    can_delete = False
    fields = ("amount_paid", "status", "payment_method", "recorded_by")


class StdSemCrsInvoiceIL(admin.TabularInline):
    """Inline list of course invoices attached to a student-semester invoice."""

    model = CrsInvoice
    fk_name = "student_semester_invoice"
    classes = ["collapse"]
    extra = 0
    can_delete = False
    show_change_link = True
    fields = (
        "curriculum_course",
        "initial_amount_due",
        "balance",
        "status",
        "created_at",
    )
    readonly_fields = ("created_at",)


# Backward-compatible alias for existing admin imports.
InvoicePaymentIL = StdSemInvoicePaymentIL
