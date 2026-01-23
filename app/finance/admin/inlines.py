"""Inline helpers for finance admin displays."""

from __future__ import annotations

from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html
from django.utils.http import urlencode

from app.finance.models.invoice import Invoice


class StudentInvoiceInline(admin.TabularInline):
    """Inline list of student invoices with payment counts."""

    model = Invoice
    fk_name = "student"
    classes = ["collapse"]
    can_delete = False
    extra = 0
    fields = (
        "semester",
        "curriculum_course",
        "amount_due",
        "payments_link",
        "created_at",
    )
    readonly_fields = ("payments_link", "created_at")

    def get_queryset(self, request):
        """Annotate invoice rows with payment counts."""
        qs = super().get_queryset(request)
        return qs.select_related("semester", "curriculum_course").annotate(
            payments_count=Count("payments")
        )

    @admin.display(description="Payments")
    def payments_link(self, obj: Invoice) -> str:
        """Return a link to filtered payments for the invoice."""
        count = getattr(obj, "payments_count", 0)
        if not count:
            return "0"
        base_url = reverse("admin:finance_payment_changelist")
        query = urlencode({"invoice__id__exact": obj.id})
        return format_html('<a href="{}?{}">{}</a>', base_url, query, count)
