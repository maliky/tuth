"""Tests for SmartSchool finance payment import."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.core.management import call_command

from app.finance.models.invoice import StdSemesterInvoice
from app.finance.models.payment import Payment

pytestmark = pytest.mark.django_db

PAYMENT_HEADERS = [
    "academic_year",
    "semester_no",
    "student_id",
    "amount_paid",
    "payment_method",
    "payer",
    "status",
    "reference",
]


def _write_payments(path: Path, rows: list[dict[str, str]]) -> None:
    """Write payment rows as import-ready TSV."""
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(PAYMENT_HEADERS) + "\n")
        for row in rows:
            handle.write(
                "\t".join(row.get(header, "") for header in PAYMENT_HEADERS) + "\n"
            )


def _payment_row(**overrides: str) -> dict[str, str]:
    """Return one valid payment import row."""
    row = {
        "academic_year": "2025/2026",
        "semester_no": "1",
        "student_id": "TU-PAY-1",
        "amount_paid": "25.00",
        "payment_method": "cash",
        "payer": "student",
        "status": "cleared",
        "reference": "R1",
    }
    row.update(overrides)
    return row


def test_import_finance_payments_creates_duplicate_amount_rows(tmp_path: Path) -> None:
    """Fresh rebuild imports every payment row, even repeated same amounts."""
    call_command("create_states", verbosity=0)
    tsv_path = tmp_path / "finance_payments.tsv"
    _write_payments(tsv_path, [_payment_row(), _payment_row(reference="R2")])

    call_command("import_finance_payments", file=tsv_path, batch_size=1)

    assert Payment.objects.count() == 2
    assert StdSemesterInvoice.objects.count() == 1


def test_import_finance_payments_dry_run_rolls_back(tmp_path: Path) -> None:
    """Payment dry-run should validate rows without creating payments."""
    call_command("create_states", verbosity=0)
    tsv_path = tmp_path / "finance_payments.tsv"
    _write_payments(tsv_path, [_payment_row()])

    call_command("import_finance_payments", file=tsv_path, dry_run=True)

    assert Payment.objects.count() == 0
    assert StdSemesterInvoice.objects.count() == 0
