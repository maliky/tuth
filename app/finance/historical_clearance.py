"""Historical invoice clearance service for finance reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import re
from typing import TypeAlias

from django.core.management.base import CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from app.finance.historical_clearance_audit import AuditRowT, audit_row, write_audit_rows
from app.finance.models.invoice import StdSemesterInvoice
from app.finance.models.payment import Payment
from app.finance.models.status_types_methods import (
    InvoiceStatus,
    Payer,
    PaymentMethod,
    PaymentStatus,
)
from app.people.models.student import Student
from app.timetable.models.semester import Semester
from app.timetable.utils import normalize_academic_year

DEFAULT_CUTOFF_SEMESTER = "25-26-S3"
DEFAULT_LOG_DIR = Path("logs/finance_reconciliation")
StatsT: TypeAlias = dict[str, int]


@dataclass(frozen=True)
class ClearanceResult:
    """Result of one parent-invoice reconciliation attempt."""

    action: str
    status: str
    payment_id: int | None
    payment_ids: tuple[int, ...]
    previous_balance: Decimal
    message: str


@dataclass(frozen=True)
class ClearanceRunResult:
    """Summary of one historical clearance run."""

    applied: bool
    scope_label: str
    stats: StatsT
    log_path: Path

    def summary(self) -> str:
        """Return a CLI-friendly summary line."""
        mode = "Applied" if self.applied else "Dry-run"
        return (
            f"{mode} invoice clearance for {self.scope_label}: "
            f"{self.stats['processed']} processed, {self.stats['cleared']} cleared, "
            f"{self.stats['would_clear']} would-clear, "
            f"{self.stats['conflict']} conflict, {self.stats['skipped']} skipped. "
            f"Audit: {self.log_path}"
        )


def reconcile_historical_clearance(
    *,
    cutoff_semester_code: str = DEFAULT_CUTOFF_SEMESTER,
    student_token: str = "",
    raw_log_path: str = "",
    apply_changes: bool = False,
    all_open: bool = False,
) -> ClearanceRunResult:
    """Run historical invoice clearance and write an audit CSV."""
    cutoff_semester = None if all_open else _resolve_cutoff_semester(cutoff_semester_code)
    selected_student_id = (
        _resolve_student_id(student_token.strip()) if student_token.strip() else None
    )
    log_path = _resolve_log_path(raw_log_path.strip())
    _ensure_finance_defaults()

    parent_invoices = _target_parent_invoices(cutoff_semester, selected_student_id)
    audit_rows: list[AuditRowT] = []
    stats = _empty_stats()
    for parent_invoice in parent_invoices:
        result = _reconcile_parent_invoice(parent_invoice.id, apply_changes)
        stats["processed"] += 1
        stats[result.status if result.status in stats else "skipped"] += 1
        audit_rows.append(audit_row(parent_invoice, result))

    write_audit_rows(log_path, audit_rows)
    scope_label = "all open semesters"
    if cutoff_semester is not None:
        scope_label = (
            f"semesters before {cutoff_semester.academic_year.code}-S"
            f"{cutoff_semester.number}"
        )
    return ClearanceRunResult(
        applied=apply_changes,
        scope_label=scope_label,
        stats=stats,
        log_path=log_path,
    )


def _empty_stats() -> StatsT:
    """Return zeroed counters for one clearance run."""
    return {"processed": 0, "would_clear": 0, "cleared": 0, "conflict": 0, "skipped": 0}


def _ensure_finance_defaults() -> None:
    """Create lookup rows needed by payment writes."""
    InvoiceStatus._populate_attributes_and_db()
    PaymentStatus._populate_attributes_and_db()
    PaymentMethod._populate_attributes_and_db()
    Payer._populate_attributes_and_db()


def _resolve_cutoff_semester(raw_value: str) -> Semester:
    """Resolve a cutoff code such as ``25-26-S3`` to a semester row."""
    match = re.fullmatch(
        r"\s*(?P<year>(?:\d{2}|\d{4})[-/](?:\d{2}|\d{4}))[-_\s]*S(?P<number>\d+)\s*",
        raw_value.upper(),
    )
    if match is None:
        raise CommandError("Use --cutoff-semester in the form 25-26-S3.")
    year_code = normalize_academic_year(match.group("year"))
    semester_number = int(match.group("number"))
    semester = (
        Semester.objects.filter(academic_year__code=year_code, number=semester_number)
        .select_related("academic_year")
        .first()
    )
    if semester is None:
        raise CommandError(f"Cutoff semester not found: {year_code}-S{semester_number}")
    return semester


def _resolve_student_id(token: str) -> int:
    """Resolve a student selector to a database id."""
    query = Q(user__username=token) | Q(username=token) | Q(student_id=token)
    if token.isdigit():
        query |= Q(id=int(token))
    student = Student.objects.filter(query).order_by("id").first()
    if student is None:
        raise CommandError(f"Student not found: {token}")
    return int(student.id)


def _resolve_log_path(raw_path: str) -> Path:
    """Return the audit CSV path for this run."""
    if raw_path:
        return Path(raw_path)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_LOG_DIR / f"historical_invoice_clearance_{timestamp}.csv"


def _semester_is_before(candidate: Semester, cutoff: Semester) -> bool:
    """Return True when candidate is before the cutoff semester."""
    candidate_start = candidate.start_date or candidate.academic_year.start_date
    cutoff_start = cutoff.start_date or cutoff.academic_year.start_date
    if candidate_start != cutoff_start:
        return candidate_start < cutoff_start
    return int(candidate.number) < int(cutoff.number)


def _target_parent_invoices(
    cutoff_semester: Semester | None,
    student_id: int | None,
) -> list[StdSemesterInvoice]:
    """Return open parent invoices for the selected reconciliation scope."""
    qs = (
        StdSemesterInvoice.objects.filter(balance__gt=Decimal("0.00"))
        .select_related("student", "student__user", "semester", "semester__academic_year")
        .order_by("semester__start_date", "student__student_id", "id")
    )
    if student_id is not None:
        qs = qs.filter(student_id=student_id)
    if cutoff_semester is None:
        return list(qs)
    return [
        parent_invoice
        for parent_invoice in qs
        if _semester_is_before(parent_invoice.semester, cutoff_semester)
    ]


def _reconcile_parent_invoice(
    parent_invoice_id: int,
    apply_changes: bool,
) -> ClearanceResult:
    """Clear one parent invoice or report the action that would be taken."""
    parent_invoice = StdSemesterInvoice.objects.get(pk=parent_invoice_id)
    previous_balance = parent_invoice.get_balance()
    if previous_balance <= Decimal("0.00"):
        return _result("skip_zero_balance", "skipped", None, (), previous_balance)
    pending_payments = _pending_payments(parent_invoice)
    pending_total = sum(
        (payment.amount_paid for payment in pending_payments), Decimal("0.00")
    )
    action = _clearance_action(
        pending_count=len(pending_payments),
        pending_total=pending_total,
        previous_balance=previous_balance,
        dry_run=True,
    )
    payment_ids = tuple(int(payment.id) for payment in pending_payments)
    payment_id = payment_ids[0] if payment_ids else None
    if not apply_changes:
        return _result(action, "would_clear", payment_id, payment_ids, previous_balance)
    return _apply_parent_invoice_clearance(parent_invoice_id)


def _apply_parent_invoice_clearance(parent_invoice_id: int) -> ClearanceResult:
    """Persist the payment mutation for one parent invoice."""
    with transaction.atomic():
        parent_invoice = StdSemesterInvoice.objects.select_for_update().get(
            pk=parent_invoice_id
        )
        parent_invoice.refresh_totals_from_sources(save_model=True)
        previous_balance = parent_invoice.get_balance()
        if previous_balance <= Decimal("0.00"):
            return _result("skip_zero_balance", "skipped", None, (), previous_balance)
        payment_ids: list[int] = []
        pending_payments = _pending_payments(parent_invoice, lock=True)
        pending_total = sum(
            (payment.amount_paid for payment in pending_payments), Decimal("0.00")
        )
        # Preserve pending payment amounts as audit history, then add a top-up only
        # for any remaining balance.
        for payment in pending_payments:
            payment.status_id = "cleared"
            payment.payment_method_id = "cash"
            payment.payer_id = "student"
            payment.save()
            payment_ids.append(int(payment.id))
        parent_invoice.refresh_from_db()
        parent_invoice.refresh_totals_from_sources(save_model=True)
        remaining_balance = parent_invoice.get_balance()
        if remaining_balance > Decimal("0.00"):
            payment = Payment(
                student_semester_invoice=parent_invoice,
                amount_paid=remaining_balance,
                status_id="cleared",
                payment_method_id="cash",
                payer_id="student",
            )
            payment.save()
            payment_ids.append(int(payment.id))
        _assert_parent_cleared(parent_invoice.id)
        action = _clearance_action(
            pending_count=len(pending_payments),
            pending_total=pending_total,
            previous_balance=previous_balance,
            dry_run=False,
        )
        payment_id = payment_ids[-1] if payment_ids else None
        return _result(
            action,
            "cleared",
            payment_id,
            tuple(payment_ids),
            previous_balance,
        )


def _pending_payments(
    parent_invoice: StdSemesterInvoice,
    *,
    lock: bool = False,
) -> list[Payment]:
    """Return pending payments for one parent invoice."""
    qs = Payment.objects.filter(
        student_semester_invoice=parent_invoice,
        status_id="pending",
    ).order_by("id")
    if lock:
        qs = qs.select_for_update()
    return list(qs)


def _clearance_action(
    *,
    pending_count: int,
    pending_total: Decimal,
    previous_balance: Decimal,
    dry_run: bool,
) -> str:
    """Return an audit action label for one invoice clearance."""
    prefix = "would_" if dry_run else ""
    if not pending_count:
        return f"{prefix}create_payment"
    if pending_total >= previous_balance:
        return f"{prefix}clear_pending"
    return f"{prefix}clear_pending_and_create_payment"


def _assert_parent_cleared(parent_invoice_id: int) -> None:
    """Raise when payment propagation did not clear parent and children."""
    parent_invoice = StdSemesterInvoice.objects.get(pk=parent_invoice_id)
    open_child_count = parent_invoice.course_invoices.filter(
        balance__gt=Decimal("0.00")
    ).count()
    if parent_invoice.get_balance() != Decimal("0.00") or open_child_count:
        raise CommandError(
            f"Clearance invariant failed for parent invoice {parent_invoice.id}."
        )


def _result(
    action: str,
    status: str,
    payment_id: int | None,
    payment_ids: tuple[int, ...],
    previous_balance: Decimal,
) -> ClearanceResult:
    """Build a result with a standard human-readable message."""
    messages = {
        "cleared": "Historical invoice cleared by reconciliation command.",
        "would_clear": "Dry-run only; no payment was written.",
        "conflict": "Multiple pending payments exist; manual review required.",
        "skipped": "Parent invoice has no open balance.",
    }
    return ClearanceResult(
        action=action,
        status=status,
        payment_id=payment_id,
        payment_ids=payment_ids,
        previous_balance=previous_balance,
        message=messages.get(status, ""),
    )


__all__ = [
    "ClearanceRunResult",
    "DEFAULT_CUTOFF_SEMESTER",
    "reconcile_historical_clearance",
]
