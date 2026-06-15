"""CSV audit helpers for historical invoice clearance."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from app.finance.historical_clearance import ClearanceResult
    from app.finance.models.invoice import StdSemesterInvoice


class AuditRowT(TypedDict):
    """CSV audit row for one attempted historical clearance."""

    student_id: str
    student_name: str
    semester: str
    parent_invoice_id: str
    previous_balance: str
    payment_id: str
    action: str
    status: str
    message: str


def audit_row(
    parent_invoice: "StdSemesterInvoice",
    result: "ClearanceResult",
) -> AuditRowT:
    """Build one audit row for the CSV report."""
    semester = parent_invoice.semester
    student = parent_invoice.student
    return {
        "student_id": student.student_id or str(student.id),
        "student_name": student.long_name or student.user.get_full_name(),
        "semester": f"{semester.academic_year.code}-S{semester.number}",
        "parent_invoice_id": str(parent_invoice.id),
        "previous_balance": f"{result.previous_balance:.2f}",
        "payment_id": str(result.payment_id or ""),
        "action": result.action,
        "status": result.status,
        "message": result.message,
    }


def write_audit_rows(path: Path, rows: list[AuditRowT]) -> None:
    """Write the reconciliation audit CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = list(AuditRowT.__annotations__)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


__all__ = ["AuditRowT", "audit_row", "write_audit_rows"]
