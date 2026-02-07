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
    from app.academics.models.curriculum_course import CurriculumCourse
    from app.people.models.staffs import Staff
    from app.people.models.student import Student
    from app.timetable.models.semester import Semester

from app.finance.models.fee_stack import resolve_course_fee_stack_map
from app.finance.models.invoice import Invoice
from app.finance.models.invoice_snapshot import InvoiceSnapshot
from app.finance.models.payment import Payment
from app.academics.models.curriculum_course import TUITION_RATE_PER_CREDIT


PaymentCreateSummaryT = dict[str, int]


class InvoiceSnapshotLineT(TypedDict):
    """Single line item for invoice snapshot rendering."""

    invoice_id: int
    course_code: str
    course_title: str
    credits: int
    cost_per_credit: str
    course_cost: str
    semester_label: str


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
    invoices: Iterable[Invoice],
    recorded_by: Optional["Staff"] = None,
) -> PaymentCreateSummaryT:
    """Create pending full payments for invoices when none exist.

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
    invoice_list = list(invoices)
    if not invoice_list:
        return summary
    with transaction.atomic():
        for invoice in invoice_list:
            balance = invoice.get_balance()
            if balance <= 0:
                summary["skipped_closed"] += 1
                continue
            if Payment.objects.filter(invoice=invoice, status_id="pending").exists():
                summary["skipped_existing"] += 1
                continue
            Payment.objects.create(
                invoice=invoice, amount_paid=balance, recorded_by=recorded_by
            )
            summary["created"] += 1
    return summary


def _resolve_fee_map(
    curriculum_course: "CurriculumCourse", semester: "Semester | None"
) -> tuple[FeeMapT, FeeLabelMapT]:
    """Resolve fee amounts from stacks attached to the course."""
    # Semester is ignored by the fee-stack model; kept for call signature stability.
    _ = semester
    return resolve_course_fee_stack_map(curriculum_course.course)


def _format_currency(amount: Decimal) -> str:
    """Return a currency-formatted string without the symbol."""
    return f"{amount:.2f}"


def build_invoice_snapshot(
    invoices: Iterable[Invoice],
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

    fee_totals: FeeMapT = {}
    fee_labels: FeeLabelMapT = {}
    lines: list[InvoiceSnapshotLineT] = []
    tuition_total = Decimal("0.00")
    total_credit_hours = 0

    for invoice in invoice_list:
        curriculum_course = invoice.curriculum_course
        course = curriculum_course.course
        credits = int(curriculum_course.credit_hours.code)
        cost_per_credit = TUITION_RATE_PER_CREDIT
        course_cost = cost_per_credit * credits
        tuition_total += course_cost
        total_credit_hours += credits
        lines.append(
            {
                "invoice_id": invoice.id,
                "course_code": course.short_code or course.code or "",
                "course_title": course.title or "",
                "credits": credits,
                "cost_per_credit": _format_currency(cost_per_credit),
                "course_cost": _format_currency(course_cost),
                "semester_label": str(invoice.semester),
            }
        )
        fee_map, label_map = _resolve_fee_map(curriculum_course, invoice.semester)
        for fee_type, amount in fee_map.items():
            fee_totals[fee_type] = fee_totals.get(fee_type, Decimal("0.00")) + amount
        for fee_type, label in label_map.items():
            fee_labels[fee_type] = label

    ordered_fee_lines: list[InvoiceSnapshotFeeT] = []
    for fee_code in FEE_TYPE_ORDER:
        if fee_code in fee_totals:
            ordered_fee_lines.append(
                {
                    "label": fee_labels.get(fee_code, fee_code.replace("_", " ").title()),
                    "amount": _format_currency(fee_totals[fee_code]),
                }
            )
    remaining_fee_codes = [code for code in fee_totals if code not in FEE_TYPE_ORDER]
    for fee_code in sorted(remaining_fee_codes):
        ordered_fee_lines.append(
            {
                "label": fee_labels.get(fee_code, fee_code.replace("_", " ").title()),
                "amount": _format_currency(fee_totals[fee_code]),
            }
        )

    fees_total = sum(fee_totals.values(), Decimal("0.00"))
    total_bill = tuition_total + fees_total

    arrears = Decimal("0.00")
    if semester:
        arrears = Invoice.objects.filter(student=student).exclude(
            semester=semester
        ).aggregate(total=Sum("balance")).get("total") or Decimal("0.00")
    payments_total = Decimal("0.00")
    if invoice_list:
        payments_total = Payment.objects.filter(
            invoice_id__in=[inv.id for inv in invoice_list]
        ).aggregate(total=Sum("amount_paid")).get("total") or Decimal("0.00")
    balance = total_bill + arrears - payments_total
    if balance < Decimal("0.00"):
        balance = Decimal("0.00")

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
        "curriculum": str(student.curriculum),
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
        "required_deposit": _format_currency(total_bill * Decimal("0.40")),
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
