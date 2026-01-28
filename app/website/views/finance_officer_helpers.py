"""Helper utilities for finance officer views."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Optional, TypedDict

from django.db.models import Q, QuerySet

from app.finance.models.invoice import Invoice
from app.finance.models.payment import Payment
from app.people.models.student import Student


class StudentOptionT(TypedDict):
    """Dropdown option for finance officer student filters."""

    id: int
    label: str
    selected: bool


class InvoiceGroupT(TypedDict):
    """Invoice group keyed by student."""

    student: Student
    rows: list[Invoice]
    total_due: Decimal


class PaymentGroupT(TypedDict):
    """Payment group keyed by student."""

    student: Student
    rows: list[Payment]
    total_paid: Decimal
    pending_count: int


def finance_student_ids() -> set[int]:
    """Return student IDs with invoices or payments."""
    invoice_ids = set(Invoice.objects.values_list("student_id", flat=True))
    payment_ids = set(Payment.objects.values_list("invoice__student_id", flat=True))
    return invoice_ids | payment_ids


def finance_students(query: str | None = None) -> QuerySet[Student]:
    """Return a queryset of finance-relevant students matching a query."""
    student_ids = finance_student_ids()
    if not student_ids:
        return Student.objects.none()
    qs = Student.objects.filter(id__in=student_ids).select_related("user")
    if not query:
        return qs.none()
    qs = qs.filter(
        Q(student_id__icontains=query)
        | Q(long_name__icontains=query)
        | Q(user__first_name__icontains=query)
        | Q(user__last_name__icontains=query)
        | Q(user__username__icontains=query)
    )
    return qs.order_by("long_name")


def finance_student_by_id(student_id: int) -> Optional[Student]:
    """Return a finance-relevant student by ID."""
    student_ids = finance_student_ids()
    if not student_ids or student_id not in student_ids:
        return None
    return Student.objects.filter(id=student_id).select_related("user").first()


def build_student_options(
    students: Iterable[Student],
    selected_student_id: Optional[int],
) -> list[StudentOptionT]:
    """Build dropdown options for the student filter."""
    options: list[StudentOptionT] = []
    for student in students:
        label = student.long_name or student.user.get_full_name() or student.student_id
        student_id = student.student_id or "Pending ID"
        options.append(
            {
                "id": student.id,
                "label": f"{label} ({student_id})",
                "selected": student.id == selected_student_id,
            }
        )
    return options


def group_invoices(invoices: Iterable[Invoice]) -> list[InvoiceGroupT]:
    """Group invoices by student preserving the incoming order."""
    groups: list[InvoiceGroupT] = []
    group_lookup: dict[int, InvoiceGroupT] = {}
    for invoice in invoices:
        student_id = invoice.student_id
        group = group_lookup.get(student_id)
        if group is None:
            group = {
                "student": invoice.student,
                "rows": [],
                "total_due": Decimal("0.00"),
            }
            group_lookup[student_id] = group
            groups.append(group)
        group["rows"].append(invoice)
        group["total_due"] += invoice.get_balance()
    return groups


def group_payments(payments: Iterable[Payment]) -> list[PaymentGroupT]:
    """Group payments by student preserving the incoming order."""
    groups: list[PaymentGroupT] = []
    group_lookup: dict[int, PaymentGroupT] = {}
    for payment in payments:
        student = payment.invoice.student
        student_id = student.id
        group = group_lookup.get(student_id)
        if group is None:
            group = {
                "student": student,
                "rows": [],
                "total_paid": Decimal("0.00"),
                "pending_count": 0,
            }
            group_lookup[student_id] = group
            groups.append(group)
        group["rows"].append(payment)
        group["total_paid"] += payment.amount_paid or Decimal("0.00")
        if payment.status_id == "pending":
            group["pending_count"] += 1
    return groups


def invoice_queryset(
    selected_student_id: Optional[int],
    status_filter: str,
    semester_id: Optional[int],
) -> QuerySet[Invoice]:
    """Return the base invoice queryset for the finance officer view."""
    qs = Invoice.objects.select_related(
        "student",
        "student__user",
        "semester",
        "curriculum_course__course",
    ).order_by("-created_at")
    if selected_student_id:
        qs = qs.filter(student_id=selected_student_id)
    if semester_id:
        qs = qs.filter(semester_id=semester_id)
    if status_filter == "open":
        qs = qs.filter(balance__gt=0)
    return qs


def payment_queryset(
    selected_student_id: Optional[int],
    status_filter: str,
    semester_id: Optional[int],
) -> QuerySet[Payment]:
    """Return the base payment queryset for the finance officer view."""
    qs = Payment.objects.select_related(
        "invoice__student",
        "invoice__student__user",
        "invoice__semester",
        "invoice__curriculum_course__course",
        "status",
        "payment_method",
    ).order_by("-id")
    if selected_student_id:
        qs = qs.filter(invoice__student_id=selected_student_id)
    if semester_id:
        qs = qs.filter(invoice__semester_id=semester_id)
    if status_filter and status_filter != "all":
        qs = qs.filter(status_id=status_filter)
    return qs


def clean_int(value: str | None) -> Optional[int]:
    """Return an int for the incoming value or None."""
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None
