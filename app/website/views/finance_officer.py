"""Finance officer invoice and payment views."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional, cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from app.finance.models.invoice import Invoice
from app.finance.models.payment import Payment
from app.finance.models.status_types_methods import PaymentMethod, PaymentStatus
from app.finance.utils import create_pending_payments
from app.shared.admin.core import get_current_semester
from app.shared.auth.perms import UserRole
from app.shared.utils import parse_str
from app.timetable.models.semester import Semester
from app.website.views.finance_officer_helpers import (
    build_student_options,
    clean_int,
    finance_student_by_id,
    finance_students,
    group_invoices,
    group_payments,
    invoice_queryset,
    payment_queryset,
)

FINANCE_GROUPS = {
    UserRole.FINANCE.value.label,
    UserRole.FINANCE_OFFICER.value.label,
    UserRole.CASHIER.value.label,
}


def _require_finance_access(request: HttpRequest) -> None:
    """Raise if the request user lacks finance access."""
    user = cast(User, request.user)
    if user.is_superuser:
        return
    if user.groups.filter(name__in=FINANCE_GROUPS).exists():
        return
    raise PermissionDenied("Finance access required.")


def _parse_decimal(value: str | None) -> Optional[Decimal]:
    """Return a Decimal for the incoming value or None."""
    raw = parse_str(value)
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


@login_required
def finance_officer_student_autocomplete(request: HttpRequest) -> HttpResponse:
    """Return finance students for the select2 dropdown."""
    _require_finance_access(request)
    query = parse_str(request.GET.get("q"))
    students = finance_students(query)[:15]
    results = [
        {
            "id": student.id,
            "text": f"{student.student_id} — {student.long_name}",
        }
        for student in students
    ]
    return JsonResponse({"results": results})


@login_required
@require_POST
def finance_officer_create_payments(request: HttpRequest) -> HttpResponse:
    """Create pending payments for selected invoices."""
    _require_finance_access(request)
    raw_ids = request.POST.getlist("invoice_ids")
    invoice_ids = [clean_int(value) for value in raw_ids if clean_int(value)]
    student_id = clean_int(request.POST.get("student_id"))

    if not invoice_ids and not student_id:
        messages.warning(request, "Select at least one invoice.")
        # > What is the POST.get next ?
        return redirect(request.POST.get("next") or reverse("finance_officer_invoices"))

    if invoice_ids:
        invoices = Invoice.objects.filter(id__in=invoice_ids)
    else:
        if student_id is None:
            # >  cannot reach heare because not invoice_ids and not student_id
            messages.warning(request, "Select a student to create payments.")
            return redirect(
                request.POST.get("next") or reverse("finance_officer_invoices")
            )
        invoices = Invoice.objects.filter(student_id=student_id, balance__gt=0)
    staff = getattr(request.user, "staff", None)
    summary = create_pending_payments(invoices, recorded_by=staff)
    created = summary.get("created", 0)
    skipped_existing = summary.get("skipped_existing", 0)
    skipped_closed = summary.get("skipped_closed", 0)
    if created:
        messages.success(
            request,
            f"Created {created} pending payment(s) with full amounts.",
        )
    if skipped_existing:
        messages.info(
            request,
            f"Skipped {skipped_existing} invoice(s) with pending payments.",
        )
    if skipped_closed:
        messages.warning(
            request,
            f"Skipped {skipped_closed} invoice(s) with no balance due.",
        )
    return redirect(request.POST.get("next") or reverse("finance_officer_invoices"))


@login_required
@require_POST
def finance_officer_update_payments(request: HttpRequest) -> HttpResponse:
    """Update payment rows from the finance officer console."""
    _require_finance_access(request)
    raw_ids = request.POST.getlist("payment_ids")
    payment_ids = [clean_int(value) for value in raw_ids]
    payment_ids = [value for value in payment_ids if value]
    student_id = clean_int(request.POST.get("student_id"))
    if not payment_ids:
        messages.warning(request, "Select at least one payment to update.")
        return redirect(request.POST.get("next") or reverse("finance_officer_invoices"))
    payments = Payment.objects.filter(id__in=payment_ids)
    if student_id:
        payments = payments.filter(invoice__student_id=student_id)
    if not payments.exists():
        messages.warning(request, "No payments found for the selection.")
        return redirect(request.POST.get("next") or reverse("finance_officer_invoices"))

    staff = getattr(request.user, "staff", None)
    updated = 0
    invalid = 0
    with transaction.atomic():
        for payment in payments:
            amount_value = _parse_decimal(request.POST.get(f"amount_paid_{payment.id}"))
            status_id = parse_str(request.POST.get(f"status_{payment.id}"))
            method_id = parse_str(request.POST.get(f"method_{payment.id}"))
            if amount_value is None and not status_id and not method_id:
                continue
            if amount_value is not None and amount_value < 0:
                invalid += 1
                continue
            if amount_value is not None:
                payment.amount_paid = amount_value
            if status_id:
                payment.status_id = status_id
            if method_id:
                payment.payment_method_id = method_id
            if staff and not payment.recorded_by_id:
                payment.recorded_by = staff
            payment.save()
            updated += 1
    if updated:
        messages.success(request, f"Updated {updated} payment(s).")
    if invalid:
        messages.warning(request, f"Skipped {invalid} payment(s) with invalid amounts.")
    return redirect(request.POST.get("next") or reverse("finance_officer_invoices"))


@login_required
def finance_officer_invoices(request: HttpRequest) -> HttpResponse:
    """Render the finance officer invoice and payment console."""
    _require_finance_access(request)
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
        current_semester = get_current_semester()
        if current_semester:
            semester_id = current_semester.id

    base_params = request.GET.copy()
    base_params.pop("tab", None)
    base_params.pop("page", None)
    base_query = base_params.urlencode()
    invoice_tab_url = "?"
    if base_query:
        invoice_tab_url = f"?tab=invoices&{base_query}"
        payment_tab_url = f"?tab=payments&{base_query}"
    else:
        invoice_tab_url = "?tab=invoices"
        payment_tab_url = "?tab=payments"
    pagination_params = request.GET.copy()
    pagination_params.pop("page", None)
    if "semester" not in pagination_params and semester_id:
        pagination_params["semester"] = str(semester_id)
    # Preserve filter inputs when the "Go to page" form submits.
    pagination_hidden_fields: list[dict[str, str]] = []
    for key, values in pagination_params.lists():
        for value in values:
            pagination_hidden_fields.append({"name": key, "value": value})

    student_options = []
    selected_student_label = ""
    if selected_student_id:
        selected_student = finance_student_by_id(selected_student_id)
        if selected_student:
            student_options = build_student_options(
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

    page_number = request.GET.get("page")
    per_page = 100
    invoice_page = Paginator(invoice_qs, per_page).get_page(page_number)
    payment_page = Paginator(payment_qs, per_page).get_page(page_number)

    invoice_groups = group_invoices(invoice_page)
    payment_groups = group_payments(payment_page)

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

    context = {
        "page_title": "Finance Officer Console",
        "page_summary": "Review invoices, record payments, and clear balances.",
        "eyebrow": "Finance officer",
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
        "semester_options": semester_options,
        "invoice_groups": invoice_groups,
        "payment_groups": payment_groups,
        "invoice_page": invoice_page,
        "payment_page": payment_page,
        "current_path": request.get_full_path(),
        "invoice_tab_url": invoice_tab_url,
        "payment_tab_url": payment_tab_url,
        "pagination_query": pagination_params.urlencode(),
        "pagination_hidden_fields": pagination_hidden_fields,
        "pagination_action": request.path,
        "student_autocomplete_url": reverse("finance_officer_student_autocomplete"),
        "dashboard_url": reverse(
            "staff_role_dashboard",
            kwargs={"role": "finance_officer"},
        ),
    }
    return render(request, "website/staff/finance_officer_invoices.html", context)
