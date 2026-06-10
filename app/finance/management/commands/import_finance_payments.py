"""Import SmartSchool payment rows into student-semester invoices."""

from __future__ import annotations

import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping, TypeAlias

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from app.finance.models.invoice import StdSemesterInvoice
from app.finance.models.payment import Payment
from app.finance.models.status_types_methods import Payer, PaymentMethod, PaymentStatus
from app.people.ensures import ensure_std_sid
from app.shared.source_truth.io import read_rows
from app.shared.utils import get_in_row
from app.timetable.ensures import ensure_sem_id

RowT: TypeAlias = Mapping[str, str]
ErrorRowT: TypeAlias = tuple[int, str, RowT]
LookupModelT: TypeAlias = type[Payer] | type[PaymentMethod] | type[PaymentStatus]


class Command(BaseCommand):
    """Load finance payments from import-ready SmartSchool TSV rows."""

    help = "Import payment rows into finance.Payment using student+semester invoices."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register payment import options."""
        parser.add_argument(
            "-f",
            "--file",
            default="logs/tusis_truth/SmartSchoolDB_20260609/import_ready/finance_payments.tsv",
            help="Path to import-ready finance_payments.tsv.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of payments to insert per bulk_create batch.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse/import without committing payment rows.",
        )
        parser.add_argument(
            "--max-errors",
            type=int,
            default=25,
            help="Stop after this many row errors.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Import payment rows and refresh affected parent invoices."""
        path = Path(str(options["file"]))
        if not path.exists():
            raise CommandError(f"Missing file: {path}")
        batch_size_value = options.get("batch_size", 1000)
        batch_size = (
            batch_size_value
            if isinstance(batch_size_value, int)
            else int(str(batch_size_value))
        )
        dry_run = bool(options.get("dry_run"))
        max_errors_value = options.get("max_errors", 25)
        max_errors = (
            max_errors_value
            if isinstance(max_errors_value, int)
            else int(str(max_errors_value))
        )

        Payer._populate_attributes_and_db()
        PaymentMethod._populate_attributes_and_db()
        PaymentStatus._populate_attributes_and_db()

        rows = read_rows(path)
        created = 0
        errors: list[ErrorRowT] = []
        parent_invoice_ids: set[int] = set()
        pending: list[Payment] = []

        with transaction.atomic():
            for row_number, row in enumerate(rows, start=1):
                try:
                    payment = _payment_from_row(row)
                except Exception as exc:
                    errors.append((row_number, str(exc), row))
                    if len(errors) >= max_errors:
                        _write_payment_errors(errors)
                        raise CommandError(
                            f"Payment import stopped after {len(errors)} errors."
                        ) from exc
                    continue
                if payment.student_semester_invoice_id:
                    parent_invoice_ids.add(payment.student_semester_invoice_id)
                pending.append(payment)
                if len(pending) >= batch_size:
                    Payment.objects.bulk_create(pending, batch_size=batch_size)
                    created += len(pending)
                    pending.clear()
                    self.stdout.write(f"Processed {row_number} / {len(rows)} payments")

            if pending:
                Payment.objects.bulk_create(pending, batch_size=batch_size)
                created += len(pending)

            if errors:
                _write_payment_errors(errors)
                raise CommandError(f"Payment import failed with {len(errors)} errors.")

            for invoice in StdSemesterInvoice.objects.filter(id__in=parent_invoice_ids):
                invoice.refresh_totals_from_sources(save_model=True)

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Payment import complete{' (dry-run)' if dry_run else ''}: "
                f"{created} payments created."
            )
        )


def _payment_from_row(row: RowT) -> Payment:
    """Build one unsaved Payment object from an import-ready row."""
    student_pk = ensure_std_sid(get_in_row("student_id", row))
    semester_no = get_in_row("semester_no", row) or get_in_row("semester", row)
    semester_pk = ensure_sem_id(get_in_row("academic_year", row), semester_no)
    invoice, _ = StdSemesterInvoice.objects.get_or_create(
        student_id=student_pk,
        semester_id=semester_pk,
    )
    return Payment(
        student_semester_invoice=invoice,
        payer_id=_lookup_code(Payer, get_in_row("payer", row), default="student"),
        amount_paid=_money(get_in_row("amount_paid", row) or get_in_row("amount", row)),
        payment_method_id=_lookup_code(
            PaymentMethod, get_in_row("payment_method", row), default="cash"
        ),
        status_id=_lookup_code(
            PaymentStatus, get_in_row("status", row), default="cleared"
        ),
    )


def _money(value: str) -> Decimal:
    """Parse one payment amount."""
    token = (value or "").replace(",", "").strip()
    if not token:
        raise ValueError("missing amount_paid")
    try:
        return Decimal(token)
    except InvalidOperation as exc:
        raise ValueError(f"invalid amount_paid: {value}") from exc


def _code(value: str, *, default: str) -> str:
    """Normalize external lookup codes to SimpleTableMixin-safe values."""
    token = re.sub(r"[^a-z0-9]+", "_", (value or default).lower()).strip("_")
    return (token or default)[:30]


def _lookup_code(model: LookupModelT, value: str, *, default: str) -> str:
    """Return a lookup code, creating the SimpleTable row when needed."""
    code = _code(value, default=default)
    model.objects.get_or_create(code=code)
    return code


def _write_payment_errors(rows: list[ErrorRowT]) -> Path:
    """Write compact payment import errors for importer repair."""
    log_path = Path("logs/import_errors/import_finance_payments_errors.csv")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "row_number",
        "error",
        "student_id",
        "academic_year",
        "semester_no",
        "amount_paid",
        "payment_method",
        "reference",
    ]
    with log_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row_number, error, row in rows:
            writer.writerow(
                {
                    "row_number": row_number,
                    "error": error,
                    "student_id": get_in_row("student_id", row),
                    "academic_year": get_in_row("academic_year", row),
                    "semester_no": get_in_row("semester_no", row),
                    "amount_paid": get_in_row("amount_paid", row),
                    "payment_method": get_in_row("payment_method", row),
                    "reference": get_in_row("reference", row),
                }
            )
    return log_path
