"""Utility helpers used in the finance app."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Iterable, Optional, TypedDict, TypeAlias

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.template.loader import render_to_string
from django.utils import timezone

if TYPE_CHECKING:
    from app.people.models.staffs import Staff
    from app.people.models.student import Student
    from app.timetable.models.semester import Semester

from app.finance.models.invoice import CrsInvoice, StdSemesterInvoice
from app.finance.models.invoice_snapshot import InvoiceSnapshot
from app.finance.models.payment import Payment


PaymentCreateSummaryT = dict[str, int]
PAYER_STUDENT_CODE = "student"
PAYER_MIXED_CODE = "mixed"


class InvoiceSnapshotLineT(TypedDict):
    """Single line item for invoice snapshot rendering."""

    invoice_id: int
    course_code: str
    course_title: str
    credits: int
    cost_per_credit: str
    course_cost: str
    sem_label: str


class InvoiceSnapshotFeeT(TypedDict):
    """Fee breakdown line in invoice snapshot."""

    label: str
    amount: str


class InvoiceSnapshotPayloadT(TypedDict):
    """Snapshot payload stored for PDF rendering."""

    university_name: str
    university_address: str
    student_name: str
    student_id: str
    department: str
    curriculum: str
    present_status: str
    address: str
    academic_semester: str
    generated_at: str
    lines: list[InvoiceSnapshotLineT]
    total_credit_hours: int
    fee_lines: list[InvoiceSnapshotFeeT]
    fees_total: str
    tuition_total: str
    total_bill: str
    arrears: str
    payments: str
    balance: str
    required_deposit: str
    required_deposit_rule: str
    bank_account_name: str
    bank_account_number: str
    deposit_by_label: str
    payment_note: str
    dean_signature: str


SnapshotTotalsT: TypeAlias = dict[str, str]
FeeMapT: TypeAlias = dict[str, Decimal]
FeeLabelMapT: TypeAlias = dict[str, str]

FEE_TYPE_ORDER = [
    "activities",
    "library",
    "maintenance",
    "registration",
    "sports",
    "technology",
]


def create_pending_payments(
    invoices: Iterable[CrsInvoice],
    recorded_by: Optional["Staff"] = None,
) -> PaymentCreateSummaryT:
    """Create pending full payments for parent student-semester invoices.

    Args:
        invoices: Iterable of invoices to receive pending payments.
        recorded_by: Optional staff profile to attach to created payments.

    Returns:
        Summary counts for created and skipped payments.
    """
    summary: PaymentCreateSummaryT = {
        "created": 0,
        "skipped_existing": 0,
        "skipped_closed": 0,
    }
    parent_invoice_ids = {
        invoice.student_semester_invoice_id
        for invoice in invoices
        if invoice.student_semester_invoice_id
    }
    if not parent_invoice_ids:
        return summary
    parent_invoices = list(
        StdSemesterInvoice.objects.filter(id__in=parent_invoice_ids).only(
            "id",
            "balance",
            "initial_amount_due",
        )
    )
    with transaction.atomic():
        for parent_invoice in parent_invoices:
            parent_invoice.refresh_totals_from_sources(save_model=True)
            balance = parent_invoice.get_balance()
            if balance <= 0:
                summary["skipped_closed"] += 1
                continue
            if Payment.objects.filter(
                student_semester_invoice=parent_invoice, status_id="pending"
            ).exists():
                summary["skipped_existing"] += 1
                continue
            Payment.objects.create(
                student_semester_invoice=parent_invoice,
                payer_id=_dft_payment_payer_id(parent_invoice),
                amount_paid=balance,
                recorded_by=recorded_by,
            )
            summary["created"] += 1
    return summary


def _format_currency(amount: Decimal) -> str:
    """Return a currency-formatted string without the symbol."""
    return f"{amount:.2f}"


def _dft_payment_payer_id(parent_invoice: StdSemesterInvoice) -> str:
    """Resolve the default payer for newly created payments."""
    candidate_codes = (
        parent_invoice.fee_payer_id,
        parent_invoice.course_tuition_payer_id,
    )
    for candidate_code in candidate_codes:
        if candidate_code and candidate_code != PAYER_MIXED_CODE:
            return candidate_code
    return PAYER_STUDENT_CODE


def _ordered_fee_lines(
    fee_totals: FeeMapT,
    fee_labels: FeeLabelMapT,
) -> list[InvoiceSnapshotFeeT]:
    """Return fee lines in a stable order for snapshot rendering."""
    ordered_fee_lines: list[InvoiceSnapshotFeeT] = []
    for fee_code in FEE_TYPE_ORDER:
        if fee_code not in fee_totals:
            continue
        ordered_fee_lines.append(
            {
                "label": fee_labels.get(fee_code, fee_code.replace("_", " ").title()),
                "amount": _format_currency(fee_totals[fee_code]),
            }
        )
    remaining_fee_codes = [code for code in fee_totals if code not in FEE_TYPE_ORDER]
    for fee_code in sorted(
        remaining_fee_codes, key=lambda code: fee_labels.get(code, code)
    ):
        ordered_fee_lines.append(
            {
                "label": fee_labels.get(fee_code, fee_code.replace("_", " ").title()),
                "amount": _format_currency(fee_totals[fee_code]),
            }
        )
    return ordered_fee_lines


def build_invoice_snapshot(
    invoices: Iterable[CrsInvoice],
    *,
    student: "Student",
    semester: "Semester | None" = None,
    created_by: "Staff | None" = None,
    currency: str | None = None,
) -> InvoiceSnapshot:
    """Create an immutable invoice snapshot from invoices.

    Args:
        invoices: Iterable of invoices to snapshot.
        student: Student tied to the snapshot.
        semester: Optional semester used for the snapshot label.
        created_by: Staff member creating the snapshot.
        currency: Currency code override (defaults to settings).

    Returns:
        InvoiceSnapshot instance.
    """
    invoice_list = list(invoices)
    currency_code = str(currency or getattr(settings, "FINANCE_DEFAULT_CURRENCY", "USD"))
    generated_at = timezone.now().strftime("%b %d, %Y %H:%M")
    university_name = getattr(
        settings, "INVOICE_UNIVERSITY_NAME", "William V. S. Tubman University (WVS TU)"
    )
    university_address = getattr(
        settings,
        "INVOICE_UNIVERSITY_ADDRESS",
        "Tubman Town, Harper City, Maryland County",
    )
    bank_account_name = getattr(
        settings,
        "INVOICE_BANK_ACCOUNT_NAME",
        "William V. S. Tubman University",
    )
    bank_account_number = getattr(
        settings,
        "INVOICE_BANK_ACCOUNT_NUMBER_USD",
        "6100530812",
    )
    payment_note = getattr(
        settings,
        "INVOICE_PAYMENT_NOTE",
        "Payment could take up to 24 hours to appear in your account.",
    )
    dean_signature = getattr(settings, "INVOICE_DEAN_SIGNATURE", "Dean of Admissions")
    if semester:
        academic_semester = f"{semester.academic_year.code} Sem. {semester.number}"
    else:
        academic_semester = "All semesters"

    parent_invoice_ids = {
        invoice.student_semester_invoice_id
        for invoice in invoice_list
        if invoice.student_semester_invoice_id
    }
    parent_invoices_qs = StdSemesterInvoice.objects.filter(student=student)
    if semester:
        parent_invoices_qs = parent_invoices_qs.filter(semester=semester)
    elif parent_invoice_ids:
        parent_invoices_qs = parent_invoices_qs.filter(id__in=parent_invoice_ids)
    else:
        parent_invoices_qs = parent_invoices_qs.none()
    parent_invoices = list(
        parent_invoices_qs.select_related("semester").prefetch_related("fee_stacks")
    )

    fee_totals: FeeMapT = {}
    fee_labels: FeeLabelMapT = {}
    lines: list[InvoiceSnapshotLineT] = []
    tuition_total = Decimal("0.00")
    course_total = Decimal("0.00")
    total_credit_hours = 0

    for invoice in invoice_list:
        curriculum_course = invoice.curriculum_course
        course = curriculum_course.course
        credits = int(curriculum_course.credit_hours.code)
        tuition_amount = curriculum_course.tuition_for(invoice.semester)
        course_cost = Decimal(invoice.initial_amount_due or Decimal("0.00"))
        cost_per_credit = (course_cost / Decimal(credits)) if credits else Decimal("0.00")
        tuition_total += tuition_amount
        course_total += course_cost
        total_credit_hours += credits
        lines.append(
            {
                "invoice_id": invoice.id,
                "course_code": course.short_code or course.code or "",
                "course_title": course.title or "",
                "credits": credits,
                "cost_per_credit": _format_currency(cost_per_credit),
                "course_cost": _format_currency(course_cost),
                "sem_label": str(invoice.semester),
            }
        )

    for parent_invoice in parent_invoices:
        for fee_stack in parent_invoice.fee_stacks.all():
            stack_amount = fee_stack.total_amount_for_sem(parent_invoice.semester)
            if stack_amount <= Decimal("0.00"):
                continue
            stack_key = f"semester_stack_{fee_stack.id}"
            fee_totals[stack_key] = (
                fee_totals.get(stack_key, Decimal("0.00")) + stack_amount
            )
            fee_labels[stack_key] = fee_stack.name

    course_fee_total = course_total - tuition_total
    if course_fee_total > Decimal("0.00"):
        fee_totals["course_linked_fees"] = course_fee_total
        fee_labels["course_linked_fees"] = "Course-linked fees"

    ordered_fee_lines = _ordered_fee_lines(fee_totals, fee_labels)
    fees_total = sum(fee_totals.values(), Decimal("0.00"))
    total_bill = tuition_total + fees_total

    arrears = Decimal("0.00")
    if semester:
        arrears = StdSemesterInvoice.objects.filter(student=student).exclude(
            semester=semester
        ).aggregate(total=Sum("balance")).get("total") or Decimal("0.00")
    payments_total = Decimal("0.00")
    if parent_invoices:
        payments_total = Payment.objects.filter(
            student_semester_invoice_id__in=[parent.id for parent in parent_invoices],
            status_id="cleared",
        ).aggregate(total=Sum("amount_paid")).get("total") or Decimal("0.00")

    required_deposit = total_bill * Decimal("0.40")
    required_deposit_rule = "40.00% of your fees"
    balance = total_bill + arrears - payments_total

    if parent_invoices:
        total_bill = sum(
            (parent_invoice.initial_amount_due for parent_invoice in parent_invoices),
            Decimal("0.00"),
        )
        fees_total = max(total_bill - tuition_total, Decimal("0.00"))
        required_deposit = sum(
            (
                parent_invoice.required_deposit_amount
                for parent_invoice in parent_invoices
            ),
            Decimal("0.00"),
        )
        distinct_deposit_percents = {
            _format_currency(parent_invoice.required_deposit_percent)
            for parent_invoice in parent_invoices
        }
        if len(distinct_deposit_percents) == 1:
            required_deposit_rule = (
                f"{next(iter(distinct_deposit_percents))}% of your fees"
            )
        else:
            required_deposit_rule = "the semester-specific required percentage"
        balance = (
            sum(
                (parent_invoice.get_balance() for parent_invoice in parent_invoices),
                Decimal("0.00"),
            )
            + arrears
        )

    fee_line_total = sum(fee_totals.values(), Decimal("0.00"))
    if fee_line_total != fees_total:
        fee_totals["snapshot_adjustment"] = fees_total - fee_line_total
        fee_labels["snapshot_adjustment"] = "Semester adjustments"
        ordered_fee_lines = _ordered_fee_lines(fee_totals, fee_labels)

    if balance < Decimal("0.00"):
        balance = Decimal("0.00")

    from app.people.models.student_curriculum_enrollment import get_primary_curriculum

    curriculum_label = str(get_primary_curriculum(student))

    departments = {
        inv.curriculum_course.course.department.code
        for inv in invoice_list
        if inv.curriculum_course and inv.curriculum_course.course.department_id
    }
    if len(departments) == 1:
        department = departments.pop()
    elif departments:
        department = "Multiple"
    else:
        department = ""

    payload: InvoiceSnapshotPayloadT = {
        "university_name": str(university_name),
        "university_address": str(university_address),
        "student_name": student.long_name or student.user.get_full_name(),
        "student_id": student.student_id,
        "department": department,
        "curriculum": curriculum_label,
        "present_status": student.class_level.title(),
        "address": student.physical_address,
        "academic_semester": academic_semester,
        "generated_at": generated_at,
        "lines": lines,
        "total_credit_hours": total_credit_hours,
        "fee_lines": ordered_fee_lines,
        "fees_total": _format_currency(fees_total),
        "tuition_total": _format_currency(tuition_total),
        "total_bill": _format_currency(total_bill),
        "arrears": _format_currency(arrears),
        "payments": _format_currency(payments_total),
        "balance": _format_currency(balance),
        "required_deposit": _format_currency(required_deposit),
        "required_deposit_rule": required_deposit_rule,
        "bank_account_name": str(bank_account_name),
        "bank_account_number": str(bank_account_number),
        "deposit_by_label": f"{student.student_id} {student.long_name}",
        "payment_note": str(payment_note),
        "dean_signature": str(dean_signature),
    }

    return InvoiceSnapshot.objects.create(
        student=student,
        semester=semester,
        created_by=created_by,
        total_amount=total_bill,
        currency=currency_code,
        payload=payload,
    )


def render_invoice_snapshot_html(
    snapshot: InvoiceSnapshot,
    *,
    template_name: str = "finance/invoice_snapshot.html",
) -> str:
    """Render a HTML document from an invoice snapshot."""
    totals: SnapshotTotalsT = {
        "total_due": f"{snapshot.total_amount:.2f}",
        "currency": snapshot.currency,
    }
    context = {
        "snapshot": snapshot,
        "payload": snapshot.payload,
        "totals": totals,
    }
    return render_to_string(template_name, context)


def render_invoice_snapshot_pdf(snapshot: InvoiceSnapshot) -> bytes:
    """Render a PDF from an invoice snapshot using WeasyPrint."""
    try:
        from weasyprint import HTML
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "WeasyPrint is required to render invoice PDFs. "
            "Install it in the container before printing."
        ) from exc

    html = render_invoice_snapshot_html(snapshot)
    base_url = getattr(settings, "WEASYPRINT_BASE_URL", None)
    if base_url is None:
        base_url = getattr(settings, "STATIC_ROOT", None) or settings.BASE_DIR
    pdf_bytes = HTML(string=html, base_url=str(base_url)).write_pdf()
    return bytes(pdf_bytes)
