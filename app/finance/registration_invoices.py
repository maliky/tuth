"""Materialize finance invoices from course registrations."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, TypeAlias, TypedDict

from django.db import transaction
from django.db.models import Exists, OuterRef, QuerySet

from app.finance.models.invoice import CrsInvoice
from app.registry.models.registration import Registration

RegistrationStatusCodesT: TypeAlias = tuple[str, ...]
RegistrationInvoiceKeyT: TypeAlias = tuple[int, int, int]

INVOICEABLE_REGISTRATION_STATUSES: RegistrationStatusCodesT = (
    "pending",
    "partialy_cleared",
)


class InvoiceMaterializationSummaryT(TypedDict):
    """Summary counters for registration invoice materialization."""

    created: int
    updated: int
    existing: int
    skipped_status: int
    skipped_zero: int


class MissingRegistrationInvoiceCountsT(TypedDict):
    """Counters for missing registration invoice dashboard metrics."""

    billable: int
    fee_setup: int


def invoiceable_registration_qs(
    *,
    student_id: int | None = None,
    semester_id: int | None = None,
    missing_only: bool = True,
    statuses: RegistrationStatusCodesT = INVOICEABLE_REGISTRATION_STATUSES,
) -> QuerySet[Registration]:
    """Return registrations that should have actionable course invoices."""
    existing_invoice = CrsInvoice.objects.filter(
        student_id=OuterRef("student_id"),
        curriculum_course_id=OuterRef("section__curriculum_course_id"),
        semester_id=OuterRef("section__semester_id"),
    )
    qs = (
        Registration.objects.filter(status_id__in=statuses)
        .select_related(
            "student",
            "student__user",
            "status",
            "section",
            "section__semester",
            "section__semester__academic_year",
            "section__curriculum_course",
            "section__curriculum_course__course",
            "section__curriculum_course__credit_hours",
        )
        .prefetch_related(
            "section__curriculum_course__course__course_fee_stacks__fee_stack__fees__fee_type",
            "section__curriculum_course__course__course_fee_stacks__fee_stack__fees__effective_from_semester",
        )
        .order_by(
            "student__long_name",
            "student__student_id",
            "section__semester__academic_year__start_date",
            "section__semester__number",
            "section__curriculum_course__course__short_code",
        )
    )
    if student_id is not None:
        qs = qs.filter(student_id=student_id)
    if semester_id is not None:
        qs = qs.filter(section__semester_id=semester_id)
    if missing_only:
        qs = qs.filter(~Exists(existing_invoice))
    return qs


def missing_registration_invoice_student_ids(
    *,
    semester_id: int | None = None,
) -> set[int]:
    """Return students with invoiceable registrations missing course invoices."""
    return set(
        invoice_generation_registration_qs(semester_id=semester_id)
        .order_by()
        .values_list("student_id", flat=True)
        .distinct()
    )


def billable_missing_registration_count(
    *,
    semester_id: int | None = None,
) -> int:
    """Return positive-amount registrations missing course invoices."""
    return missing_registration_invoice_counts(semester_id=semester_id)["billable"]


def fee_setup_missing_registration_count(
    *,
    semester_id: int | None = None,
) -> int:
    """Return zero-amount registrations missing course invoices."""
    return missing_registration_invoice_counts(semester_id=semester_id)["fee_setup"]


def missing_registration_invoice_counts(
    *,
    student_id: int | None = None,
    semester_id: int | None = None,
) -> MissingRegistrationInvoiceCountsT:
    """Return missing-invoice counters with one fee-resolution pass."""
    counts: MissingRegistrationInvoiceCountsT = {"billable": 0, "fee_setup": 0}
    for registration in invoice_generation_registration_qs(
        student_id=student_id,
        semester_id=semester_id,
    ).order_by():
        if registration_invoice_amount(registration) > Decimal("0.00"):
            counts["billable"] += 1
        else:
            counts["fee_setup"] += 1
    return counts


def registration_invoice_amount(registration: Registration) -> Decimal:
    """Return the billable amount for a registration section."""
    return registration.section.fee_total_amount()


def invoice_generation_registration_qs(
    *,
    student_id: int | None = None,
    semester_id: int | None = None,
) -> QuerySet[Registration]:
    """Return registrations missing invoices or holding stale zero invoices."""
    candidate_qs = invoiceable_registration_qs(
        student_id=student_id,
        semester_id=semester_id,
        missing_only=False,
    )
    candidate_registrations = list(candidate_qs)
    if not candidate_registrations:
        return candidate_qs.none()
    existing_keys, stale_zero_keys = _invoice_key_sets(candidate_registrations)
    actionable_ids = [
        registration.id
        for registration in candidate_registrations
        if _registration_invoice_key(registration) not in existing_keys
        or _registration_invoice_key(registration) in stale_zero_keys
    ]
    if not actionable_ids:
        return candidate_qs.none()
    return candidate_qs.filter(id__in=actionable_ids)


def ensure_course_invoice_for_registration(
    registration: Registration,
) -> tuple[CrsInvoice | None, bool, bool]:
    """Ensure one course invoice exists for an invoiceable registration.

    Returns:
        Tuple of invoice, created flag, updated flag. Non-invoiceable or zero-amount
        registrations return ``(None, False, False)``.
    """
    if registration.status_id not in INVOICEABLE_REGISTRATION_STATUSES:
        return None, False, False
    amount_due = registration_invoice_amount(registration)
    if amount_due <= Decimal("0.00"):
        return None, False, False
    invoice, created = CrsInvoice.objects.get_or_create(
        student=registration.student,
        curriculum_course=registration.section.curriculum_course,
        semester=registration.section.semester,
        defaults={
            "initial_amount_due": amount_due,
            "balance": amount_due,
        },
    )
    if created:
        return invoice, True, False
    updated = _patch_invoice_amount(invoice, amount_due)
    return invoice, False, updated


def _invoice_key_sets(
    registrations: Iterable[Registration],
) -> tuple[set[RegistrationInvoiceKeyT], set[RegistrationInvoiceKeyT]]:
    """Return existing and stale-zero invoice keys for registration candidates."""
    registration_list = list(registrations)
    student_ids = {registration.student_id for registration in registration_list}
    curriculum_course_ids = {
        registration.section.curriculum_course_id for registration in registration_list
    }
    semester_ids = {
        registration.section.semester_id for registration in registration_list
    }
    invoice_qs = CrsInvoice.objects.filter(
        student_id__in=student_ids,
        curriculum_course_id__in=curriculum_course_ids,
        semester_id__in=semester_ids,
    )
    existing_keys: set[RegistrationInvoiceKeyT] = set()
    stale_zero_keys: set[RegistrationInvoiceKeyT] = set()
    for invoice in invoice_qs:
        key = (
            invoice.student_id,
            invoice.curriculum_course_id,
            invoice.semester_id,
        )
        existing_keys.add(key)
        if invoice.initial_amount_due <= Decimal(
            "0.00"
        ) and invoice.get_balance() <= Decimal("0.00"):
            stale_zero_keys.add(key)
    return existing_keys, stale_zero_keys


def _registration_invoice_key(registration: Registration) -> RegistrationInvoiceKeyT:
    """Return the matching CrsInvoice identity for a registration."""
    return (
        registration.student_id,
        registration.section.curriculum_course_id,
        registration.section.semester_id,
    )


def materialize_registration_invoices(
    registrations: Iterable[Registration],
    *,
    dry_run: bool = False,
) -> InvoiceMaterializationSummaryT:
    """Create or patch missing invoices for a set of registrations."""
    summary: InvoiceMaterializationSummaryT = {
        "created": 0,
        "updated": 0,
        "existing": 0,
        "skipped_status": 0,
        "skipped_zero": 0,
    }
    with transaction.atomic():
        for registration in registrations:
            if registration.status_id not in INVOICEABLE_REGISTRATION_STATUSES:
                summary["skipped_status"] += 1
                continue
            if registration_invoice_amount(registration) <= Decimal("0.00"):
                summary["skipped_zero"] += 1
                continue
            invoice, created, updated = ensure_course_invoice_for_registration(
                registration
            )
            if invoice is None:
                summary["skipped_zero"] += 1
            elif created:
                summary["created"] += 1
            elif updated:
                summary["updated"] += 1
            else:
                summary["existing"] += 1
        if dry_run:
            transaction.set_rollback(True)
    return summary


def _patch_invoice_amount(invoice: CrsInvoice, amount_due: Decimal) -> bool:
    """Patch stale invoice amounts without creating duplicate rows."""
    changed = False
    update_fields: list[str] = []
    previous_initial = invoice.initial_amount_due or Decimal("0.00")
    if invoice.initial_amount_due != amount_due:
        invoice.initial_amount_due = amount_due
        update_fields.append("initial_amount_due")
        changed = True
    if _invoice_balance_can_follow_initial(invoice, previous_initial, amount_due):
        invoice.balance = amount_due
        update_fields.append("balance")
        changed = True
    if invoice.student_semester_invoice_id is None:
        update_fields.append("student_semester_invoice")
        changed = True
    if not changed:
        return False
    update_fields.append("status")
    invoice.save(update_fields=update_fields)
    return True


def _invoice_balance_can_follow_initial(
    invoice: CrsInvoice,
    previous_initial: Decimal,
    amount_due: Decimal,
) -> bool:
    """Return True when a stale unpaid child invoice balance can be corrected."""
    if invoice.balance is None:
        return True
    if previous_initial == amount_due:
        return False
    if invoice.balance != previous_initial:
        return False
    parent_invoice = invoice.student_semester_invoice
    if parent_invoice is None:
        return True
    return not parent_invoice.payments.filter(status_id="cleared").exists()


__all__ = [
    "INVOICEABLE_REGISTRATION_STATUSES",
    "InvoiceMaterializationSummaryT",
    "MissingRegistrationInvoiceCountsT",
    "ensure_course_invoice_for_registration",
    "billable_missing_registration_count",
    "fee_setup_missing_registration_count",
    "invoice_generation_registration_qs",
    "invoiceable_registration_qs",
    "materialize_registration_invoices",
    "missing_registration_invoice_counts",
    "missing_registration_invoice_student_ids",
    "registration_invoice_amount",
]
