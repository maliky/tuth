"""Helper utilities for finance officer views."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Optional, TypedDict, cast

from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.urls import reverse

from app.finance.models.invoice import CrsInvoice
from app.finance.models.payment import Payment
from app.finance.models.status_types_methods import Payer, PaymentMethod, PaymentStatus
from app.people.models.student import Student
from app.timetable.models.semester import Semester
from app.website.services.portal_types import PortalContextT
from app.website.services.staff_portal import (
    build_staff_role_switcher,
    build_staff_sidebar_links,
)


class StdOptionT(TypedDict):
    """Dropdown option for finance officer student filters."""

    id: int
    label: str
    selected: bool


class InvoiceGpT(TypedDict):
    """Invoice group keyed by student."""

    student: Student
    rows: list[CrsInvoice]
    total_due: Decimal


class PaymentGpT(TypedDict):
    """Payment group keyed by student."""

    student: Student
    rows: list[Payment]
    total_paid: Decimal
    pending_count: int


def finance_std_ids() -> set[int]:
    """Return student IDs with invoices or payments."""
    invoice_ids = set(CrsInvoice.objects.values_list("student_id", flat=True))
    payment_ids = set(
        Payment.objects.values_list("student_semester_invoice__student_id", flat=True)
    )
    return invoice_ids | payment_ids


def finance_stds(query: str | None = None) -> QuerySet[Student]:
    """Return a queryset of finance-relevant students matching a query."""
    student_ids = finance_std_ids()
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


def finance_std_by_id(student_id: int) -> Optional[Student]:
    """Return a finance-relevant student by ID."""
    student_ids = finance_std_ids()
    if not student_ids or student_id not in student_ids:
        return None
    return Student.objects.filter(id=student_id).select_related("user").first()


def build_std_options(
    students: Iterable[Student],
    selected_student_id: Optional[int],
) -> list[StdOptionT]:
    """Build dropdown options for the student filter."""
    options: list[StdOptionT] = []
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


def gp_invoices(invoices: Iterable[CrsInvoice]) -> list[InvoiceGpT]:
    """Group invoices by student preserving the incoming order."""
    groups: list[InvoiceGpT] = []
    group_lookup: dict[int, InvoiceGpT] = {}
    parent_seen_by_student: dict[int, set[int]] = {}
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
            parent_seen_by_student[student_id] = set()
        group["rows"].append(invoice)
        parent_invoice_id = invoice.student_semester_invoice_id
        if parent_invoice_id is None:
            group["total_due"] += invoice.get_balance()
            continue
        if parent_invoice_id in parent_seen_by_student[student_id]:
            continue
        parent_seen_by_student[student_id].add(parent_invoice_id)
        parent_invoice = invoice.student_semester_invoice
        if parent_invoice is None:
            group["total_due"] += invoice.get_balance()
            continue
        group["total_due"] += parent_invoice.get_balance()
    return groups


def gp_payments(payments: Iterable[Payment]) -> list[PaymentGpT]:
    """Group payments by student preserving the incoming order."""
    groups: list[PaymentGpT] = []
    group_lookup: dict[int, PaymentGpT] = {}
    for payment in payments:
        student = payment.student_semester_invoice.student
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
) -> QuerySet[CrsInvoice]:
    """Return the base invoice queryset for the finance officer view."""
    qs = CrsInvoice.objects.select_related(
        "student",
        "student__user",
        "semester",
        "curriculum_course__course",
        "student_semester_invoice",
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
        "student_semester_invoice__student",
        "student_semester_invoice__student__user",
        "student_semester_invoice__semester",
        "payer",
        "status",
        "payment_method",
    ).order_by("-id")
    if selected_student_id:
        qs = qs.filter(student_semester_invoice__student_id=selected_student_id)
    if semester_id:
        qs = qs.filter(student_semester_invoice__semester_id=semester_id)
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


def build_finance_console_context(request: HttpRequest) -> PortalContextT:
    """Build context for the finance officer invoice and payment console."""
    user = cast(User, request.user)
    tab = request.GET.get("tab", "invoices")
    search_query = request.GET.get("q", "").strip()
    selected_student_id = clean_int(request.GET.get("student_id"))
    invoice_status = request.GET.get("invoice_status") or None
    payment_status = request.GET.get("payment_status") or None
    semester_param = request.GET.get("semester")
    semester_id = clean_int(semester_param)
    semester_param_present = "semester" in request.GET
    if semester_param == "all":
        semester_id = None
    if selected_student_id and invoice_status is None:
        invoice_status = "all"
    if not selected_student_id and invoice_status is None:
        invoice_status = "open"
    if selected_student_id and payment_status is None:
        payment_status = "all"
    if not selected_student_id and payment_status is None:
        payment_status = "pending"
    if not semester_param_present:
        current_semester = Semester.get_current_sem()
        if current_semester:
            semester_id = current_semester.id

    base_params = request.GET.copy()
    base_params.pop("tab", None)
    base_params.pop("page", None)
    base_query = base_params.urlencode()
    if base_query:
        invoice_tab_url = f"?tab=invoices&{base_query}"
        payment_tab_url = f"?tab=payments&{base_query}"
    else:
        invoice_tab_url = "?tab=invoices"
        payment_tab_url = "?tab=payments"
    invoice_all_url = "?tab=invoices&invoice_status=all&semester=all"
    payment_all_url = "?tab=payments&payment_status=all&semester=all"
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    if "semester" not in pagination_params and semester_id:
        pagination_params["semester"] = str(semester_id)
    pagination_hidden_fields: list[dict[str, str]] = []
    for key, values in pagination_params.lists():
        for value in values:
            pagination_hidden_fields.append({"name": key, "value": value})

    student_options = []
    selected_student_label = ""
    if selected_student_id:
        selected_student = finance_std_by_id(selected_student_id)
        if selected_student:
            student_options = build_std_options(
                [selected_student],
                selected_student_id,
            )
            selected_student_label = student_options[0]["label"]
    invoice_qs = invoice_queryset(
        selected_student_id,
        invoice_status or "open",
        semester_id,
    )
    payment_qs = payment_queryset(
        selected_student_id,
        payment_status or "pending",
        semester_id,
    )

    invoice_page = Paginator(invoice_qs, 100).get_page(request.GET.get("page"))
    payment_page = Paginator(payment_qs, 100).get_page(request.GET.get("page"))

    invoice_status_options = [
        {"value": "open", "label": "Open balance"},
        {"value": "all", "label": "All invoices"},
    ]
    payment_status_options = [
        {"value": "all", "label": "All payments"},
    ] + [
        {"value": status.code, "label": status.label}
        for status in PaymentStatus.objects.order_by("label")
    ]
    payment_status_choices = [
        {"code": status.code, "label": status.label}
        for status in PaymentStatus.objects.order_by("label")
    ]
    payment_method_options = [
        {"code": method.code, "label": method.label}
        for method in PaymentMethod.objects.order_by("label")
    ]
    payer_options = [
        {"code": payer.code, "label": payer.label}
        for payer in Payer.objects.order_by("label")
    ]
    semester_options = [
        {
            "value": "all",
            "label": "All semesters",
            "selected": semester_param == "all",
        }
    ]
    for sem in Semester.objects.select_related("academic_year").order_by(
        "-academic_year__start_date",
        "-number",
    ):
        semester_options.append(
            {
                "value": str(sem.id),
                "label": f"{sem.academic_year.code} · Semester {sem.number}",
                "selected": semester_id == sem.id,
            }
        )

    active_task = "payment_validation" if tab == "payments" else "invoice_console"
    dashboard_url = reverse(
        "staff_role_dashboard",
        kwargs={"role": "finance_officer"},
    )
    return {
        "page_title": "Finance Officer Console",
        "page_summary": "Review invoices, record payments, and clear balances.",
        "eyebrow": "Finance officer",
        "sidebar_links": build_staff_sidebar_links("finance_officer", active_task),
        "role_switcher": build_staff_role_switcher(user, "finance_officer"),
        "breadcrumbs": [
            {"label": "Finance overview", "href": dashboard_url},
            {"label": "Invoice console", "href": ""},
        ],
        "active_tab": tab,
        "search_query": search_query,
        "student_options": student_options,
        "selected_student_id": selected_student_id,
        "selected_student_label": selected_student_label,
        "invoice_status": invoice_status,
        "payment_status": payment_status,
        "invoice_status_options": invoice_status_options,
        "payment_status_options": payment_status_options,
        "payment_status_choices": payment_status_choices,
        "payment_method_options": payment_method_options,
        "payer_options": payer_options,
        "semester_options": semester_options,
        "invoice_groups": gp_invoices(invoice_page),
        "payment_groups": gp_payments(payment_page),
        "invoice_page": invoice_page,
        "payment_page": payment_page,
        "current_path": request.get_full_path(),
        "invoice_tab_url": invoice_tab_url,
        "payment_tab_url": payment_tab_url,
        "invoice_all_url": invoice_all_url,
        "payment_all_url": payment_all_url,
        "pagination_query": pagination_params.urlencode(),
        "pagination_hidden_fields": pagination_hidden_fields,
        "pagination_action": request.path,
        "student_autocomplete_url": reverse("finance_officer_std_autocomplete"),
        "dashboard_url": dashboard_url,
    }
