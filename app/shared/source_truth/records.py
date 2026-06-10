"""Extract non-catalog operational witnesses for source-truth builds."""

from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

from app.shared.source_truth.io import RowT, read_rows

RowsT: TypeAlias = list[RowT]


def load_smartschool_payments(smartschool_dir: Path, ok_tables: set[str]) -> RowsT:
    """Load latest SmartSchool payments when its export passed integrity."""
    if "payments" not in ok_tables:
        return []
    path = smartschool_dir / "dbo_payments.csv"
    rows: RowsT = []
    for row in read_rows(path):
        rows.append(
            {
                "source_name": "latest_smartschool",
                "source_path": str(path),
                "academic_year": _first(row, "AcademicYear"),
                "semester": _first(row, "Semester"),
                "date": _first(row, "Date"),
                "student_id": _first(row, "StudentID"),
                "amount": _first(row, "Amount"),
                "payment_type": _first(row, "PaymentType"),
                "donor": _first(row, "Donor"),
                "reference": _first(row, "Reference", "Sysref"),
            }
        )
    return rows


def load_fundamental_students(fundamentals_dir: Path) -> RowsT:
    """Load historical SmartSchool student witnesses."""
    path = fundamentals_dir / "people_full_student.tsv"
    rows: RowsT = []
    for row in read_rows(path):
        rows.append(
            {
                "source_name": "fundamentals_smartschool",
                "source_path": str(path),
                "student_id": _first(row, "student_id", "StudentID"),
                "student_name": _first(row, "long_name", "student_name"),
                "curriculum": _first(row, "curriculum"),
                "college_code": _first(row, "college_code"),
                "username": _first(row, "username"),
            }
        )
    return rows


def load_grapro_students(grapro_dir: Path) -> RowsT:
    """Load GradPro student/account name witnesses."""
    path = grapro_dir / "Accounts.csv"
    rows: RowsT = []
    for row in read_rows(path):
        if _first(row, "AccountType").lower() != "student":
            continue
        name = _name_from_parts(
            _first(row, "FirstName"), _first(row, "MiddleName"), _first(row, "LastName")
        )
        rows.append(
            {
                "source_name": "grapro_legacy",
                "source_path": str(path),
                "student_id": _first(row, "AccountID"),
                "student_name": name,
                "curriculum": _first(row, "ProgramID"),
                "college_code": "",
                "username": "",
            }
        )
    return rows


def load_passthrough_rows(path: Path, source_name: str) -> RowsT:
    """Load rows intended to be copied to import-ready outputs."""
    rows: RowsT = []
    for row in read_rows(path):
        out = dict(row)
        out["source_name"] = source_name
        out["source_path"] = str(path)
        rows.append(out)
    return rows


def _first(row: RowT, *keys: str) -> str:
    """Return the first non-empty value from row by candidate column name."""
    for key in keys:
        value = row.get(key, "")
        if value:
            return value.strip()
    return ""


def _name_from_parts(first: str, middle: str, last: str) -> str:
    """Join name parts while dropping blanks."""
    return " ".join(part for part in (first, middle, last) if part).strip()
