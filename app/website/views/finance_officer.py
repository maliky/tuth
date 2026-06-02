"""Finance officer invoice and payment views."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional, cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from app.finance.models.invoice import CrsInvoice
from app.finance.models.payment import Payment
from app.finance.models.status_types_methods import Payer
from app.finance.utils import create_pending_payments
from app.shared.auth.perms import UserRole
from app.shared.utils import parse_str
from app.website.services.finance_portal import (
    build_finance_console_context,
    clean_int,
    finance_stds,
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
def finance_officer_std_autocomplete(request: HttpRequest) -> HttpResponse:
    """Return finance students for the select2 dropdown."""
    _require_finance_access(request)
    query = parse_str(request.GET.get("q"))
    students = finance_stds(query)[:15]
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
        invoices = CrsInvoice.objects.filter(id__in=invoice_ids)
    else:
        if student_id is None:
            # >  cannot reach heare because not invoice_ids and not student_id
            messages.warning(request, "Select a student to create payments.")
            return redirect(
                request.POST.get("next") or reverse("finance_officer_invoices")
            )
        invoices = CrsInvoice.objects.filter(student_id=student_id, balance__gt=0)
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
        payments = payments.filter(student_semester_invoice__student_id=student_id)
    if not payments.exists():
        messages.warning(request, "No payments found for the selection.")
        return redirect(request.POST.get("next") or reverse("finance_officer_invoices"))

    staff = getattr(request.user, "staff", None)
    valid_payer_ids = set(Payer.objects.values_list("code", flat=True))
    updated = 0
    invalid = 0
    with transaction.atomic():
        for payment in payments:
            amount_value = _parse_decimal(request.POST.get(f"amount_paid_{payment.id}"))
            status_id = parse_str(request.POST.get(f"status_{payment.id}"))
            method_id = parse_str(request.POST.get(f"method_{payment.id}"))
            payer_id = parse_str(request.POST.get(f"payer_{payment.id}"))
            if amount_value is None and not status_id and not method_id and not payer_id:
                continue
            if amount_value is not None and amount_value < 0:
                invalid += 1
                continue
            if payer_id and payer_id not in valid_payer_ids:
                invalid += 1
                continue
            if amount_value is not None:
                payment.amount_paid = amount_value
            if status_id:
                payment.status_id = status_id
            if method_id:
                payment.payment_method_id = method_id
            if payer_id:
                payment.payer_id = payer_id
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
    context = build_finance_console_context(request)
    return render(request, "website/staff/finance_officer_invoices.html", context)
