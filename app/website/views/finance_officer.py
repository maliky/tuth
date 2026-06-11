"""Finance officer invoice and payment views."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Optional, TypedDict, cast

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
from app.finance.course_fee_setup import ensure_course_default_fee
from app.finance.registration_invoices import (
    ensure_course_invoice_for_registration,
    invoice_generation_registration_qs,
    invoiceable_registration_qs,
    materialize_registration_invoices,
)
from app.finance.models.status_types_methods import (
    InvoiceStatus,
    Payer,
    PaymentMethod,
    PaymentStatus,
)
from app.finance.utils import create_pending_payments
from app.registry.models.registration import Registration
from app.shared.auth.perms import UserRole
from app.shared.utils import parse_str
from app.website.services.finance_portal import (
    build_finance_console_context,
    clean_int,
    finance_stds,
)

if TYPE_CHECKING:
    from app.people.models.staffs import Staff

FINANCE_GROUPS = {
    UserRole.FINANCE.value.label,
    UserRole.FINANCE_OFFICER.value.label,
    UserRole.CASHIER.value.label,
}


class CourseInvoiceStateT(TypedDict):
    """Snapshot of a child invoice before targeted payment propagation."""

    invoice_id: int
    balance: Decimal | None
    status_id: str


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
@require_POST
def finance_officer_generate_registration_invoices(request: HttpRequest) -> HttpResponse:
    """Create course invoices for imported registrations missing finance rows."""
    _require_finance_access(request)
    raw_ids = request.POST.getlist("registration_ids")
    registration_ids = [clean_int(value) for value in raw_ids]
    registration_ids = [value for value in registration_ids if value]
    student_id = clean_int(request.POST.get("student_id"))
    if registration_ids:
        registrations = invoiceable_registration_qs(missing_only=False).filter(
            id__in=registration_ids
        )
    elif student_id:
        registrations = invoice_generation_registration_qs(student_id=student_id)
    else:
        messages.warning(request, "Select registrations or a student to invoice.")
        return redirect(request.POST.get("next") or reverse("finance_officer_invoices"))

    if not registrations.exists():
        messages.info(request, "No uninvoiced registrations were found.")
        return redirect(request.POST.get("next") or reverse("finance_officer_invoices"))

    summary = materialize_registration_invoices(registrations)
    created = summary["created"]
    updated = summary["updated"]
    skipped_zero = summary["skipped_zero"]
    if created or updated:
        messages.success(
            request,
            f"Generated {created} invoice(s); updated {updated} existing invoice(s).",
        )
    if skipped_zero:
        messages.info(
            request,
            f"Skipped {skipped_zero} zero-amount registration(s).",
        )
    if not created and not updated and not skipped_zero:
        messages.info(request, "No invoices needed to be generated.")
    return redirect(request.POST.get("next") or reverse("finance_officer_invoices"))


@login_required
@require_POST
def finance_officer_setup_registration_fee(request: HttpRequest) -> HttpResponse:
    """Set a course fee, generate its invoice, and optionally clear it."""
    _require_finance_access(request)
    registration_id = clean_int(request.POST.get("registration_id"))
    amount = _parse_decimal(request.POST.get("amount"))
    fee_type_code = parse_str(request.POST.get("fee_type_code"))
    clear_now = request.POST.get("clear_now") == "1"
    if registration_id is None or amount is None or amount <= Decimal("0.00"):
        messages.warning(request, "Provide a registration and a positive fee amount.")
        return redirect(request.POST.get("next") or reverse("finance_officer_invoices"))

    registration = (
        invoiceable_registration_qs(missing_only=False).filter(id=registration_id).first()
    )
    if registration is None:
        messages.warning(request, "No invoiceable registration was found.")
        return redirect(request.POST.get("next") or reverse("finance_officer_invoices"))

    staff = getattr(request.user, "staff", None)
    with transaction.atomic():
        current_amount = registration.section.fee_total_amount()
        additional_amount = amount - current_amount
        if additional_amount > Decimal("0.00"):
            ensure_course_default_fee(
                course=registration.section.curriculum_course.course,
                amount=additional_amount,
                fee_type_code=fee_type_code,
            )
        invoice, created, updated = ensure_course_invoice_for_registration(registration)
        if invoice is None or invoice.student_semester_invoice is None:
            messages.warning(request, "The fee was saved but no invoice was generated.")
            return redirect(
                request.POST.get("next") or reverse("finance_officer_invoices")
            )
        parent_invoice = invoice.student_semester_invoice
        parent_invoice.refresh_totals_from_sources(save_model=True)
        cleared = _clear_course_invoice(invoice, staff) if clear_now else False

    if clear_now and cleared:
        messages.success(request, "Fee, invoice, and cleared payment were recorded.")
    elif created:
        messages.success(request, "Fee was set and one invoice was generated.")
    elif updated:
        messages.success(request, "Fee was set and the existing invoice was updated.")
    else:
        messages.info(request, "Fee setup is already reflected in the invoice.")
    return redirect(request.POST.get("next") or reverse("finance_officer_invoices"))


def _clear_course_invoice(
    invoice: CrsInvoice,
    staff: "Staff | None",
) -> bool:
    """Create a cleared payment for one course invoice without clearing siblings."""
    parent_invoice = invoice.student_semester_invoice
    if parent_invoice is None:
        return False
    PaymentStatus._populate_attributes_and_db()
    PaymentMethod._populate_attributes_and_db()
    InvoiceStatus._populate_attributes_and_db()
    invoice.refresh_from_db()
    balance = invoice.get_balance()
    if balance <= Decimal("0.00"):
        return False
    sibling_states = _course_invoice_states(parent_invoice.id, invoice.id)
    Payment.objects.create(
        student_semester_invoice=parent_invoice,
        payer_id="student",
        amount_paid=balance,
        payment_method_id="cash",
        status_id="cleared",
        recorded_by=staff,
    )
    _restore_course_invoice_states(sibling_states)
    _mark_course_invoice_cleared(invoice.id)
    return True


def _course_invoice_states(
    parent_invoice_id: int,
    target_invoice_id: int,
) -> list[CourseInvoiceStateT]:
    """Snapshot sibling invoices before parent payment redistribution runs."""
    states: list[CourseInvoiceStateT] = []
    siblings = CrsInvoice.objects.filter(
        student_semester_invoice_id=parent_invoice_id,
    ).exclude(pk=target_invoice_id)
    for sibling in siblings.only("id", "balance", "status"):
        states.append(
            {
                "invoice_id": sibling.id,
                "balance": sibling.balance,
                "status_id": sibling.status_id or "initial",
            }
        )
    return states


def _restore_course_invoice_states(states: list[CourseInvoiceStateT]) -> None:
    """Restore sibling invoice rows after parent-level payment propagation."""
    for state in states:
        CrsInvoice.objects.filter(pk=state["invoice_id"]).update(
            balance=state["balance"],
            status_id=state["status_id"],
        )
        invoice = CrsInvoice.objects.get(pk=state["invoice_id"])
        _force_registration_status_for_invoice(invoice)


def _mark_course_invoice_cleared(invoice_id: int) -> None:
    """Persist a cleared child invoice and sync its registration status."""
    CrsInvoice.objects.filter(pk=invoice_id).update(
        balance=Decimal("0.00"),
        status_id=InvoiceStatus.cleared().code,
    )
    invoice = CrsInvoice.objects.get(pk=invoice_id)
    _force_registration_status_for_invoice(invoice)


def _force_registration_status_for_invoice(invoice: CrsInvoice) -> int:
    """Set registration status from an invoice, including rollback from cleared."""
    reg_status_id = _registration_status_id_for_invoice(invoice.status_id or "initial")
    return Registration.objects.filter(
        student=invoice.student,
        section__curriculum_course=invoice.curriculum_course,
        section__semester=invoice.semester,
    ).update(status_id=reg_status_id)


def _registration_status_id_for_invoice(status_id: str) -> str:
    """Map course invoice status IDs to registration status IDs."""
    if status_id in {"initial", "updated"}:
        return "pending"
    if status_id == "settled":
        return "partialy_cleared"
    return "cleared"


@login_required
def finance_officer_invoices(request: HttpRequest) -> HttpResponse:
    """Render the finance officer invoice and payment console."""
    _require_finance_access(request)
    context = build_finance_console_context(request)
    return render(request, "website/staff/finance_officer_invoices.html", context)
