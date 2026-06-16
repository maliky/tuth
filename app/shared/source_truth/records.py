"""Extract non-catalog operational witnesses for source-truth builds."""

from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

from app.people.utils import mk_username
from app.shared.source_truth.curriculum_match import (
    standardize_legacy_curriculum_label,
)
from app.shared.source_truth.grapro_normalize import (
    gradpro_date_value,
    gradpro_semester_code,
    gradpro_term_parts,
)
from app.shared.source_truth.college_codes import (
    canonical_college_code,
    canonicalize_college_fields,
)
from app.shared.source_truth.io import RowT, read_rows
from app.shared.source_truth.smartschool_normalize import semester_no

RowsT: TypeAlias = list[RowT]


def load_smartschool_payments(smartschool_dir: Path, ok_tables: set[str]) -> RowsT:
    """Load latest SmartSchool payments when its export passed integrity."""
    if "payments" not in ok_tables:
        return []
    path = smartschool_dir / "dbo_payments.csv"
    rows: RowsT = []
    for row in read_rows(path):
        raw_payment_type = _first(row, "PaymentType")
        rows.append(
            {
                "source_name": "latest_smartschool",
                "source_path": str(path),
                "academic_year": _first(row, "AcademicYear"),
                "semester_no": semester_no(_first(row, "Semester")),
                "date": _first(row, "Date"),
                "student_id": _first(row, "StudentID"),
                "amount_paid": _first(row, "Amount"),
                "payment_method": raw_payment_type.lower() or "cash",
                "payment_type": raw_payment_type,
                "payer": "student",
                "status": "cleared",
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
                "college_code": canonical_college_code(_first(row, "college_code")),
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


def load_grapro_import_students(grapro_dir: Path) -> RowsT:
    """Load GradPro student accounts in the StudentResource import shape."""
    path = grapro_dir / "Accounts.csv"
    info_by_id = _grapro_student_info(grapro_dir)
    rows: RowsT = []
    seen_usernames: set[str] = set()
    for row in read_rows(path):
        if _first(row, "AccountType").lower() != "student":
            continue
        student_id = _first(row, "AccountID")
        if not student_id:
            continue
        info = info_by_id.get(student_id, {})
        first = _first(row, "FirstName")
        middle = _first(row, "MiddleName")
        last = _first(row, "LastName") or student_id
        legacy_curriculum = _first(row, "ProgramID")
        rows.append(
            {
                "source_name": "grapro_legacy",
                "source_path": str(path),
                "long_name": _name_from_parts(first, middle, last),
                "first_name": first,
                "middle_name": middle,
                "last_name": last,
                "student_id": student_id,
                "curriculum": standardize_legacy_curriculum_label(legacy_curriculum),
                "legacy_curriculum": legacy_curriculum,
                "college_code": "",
                "bio_ClassLevel": _first(info, "ClassLevel"),
                "bio_EnrollmentStatusID": _first(info, "EnrollmentStatusID"),
                "birth_date": gradpro_date_value(_first(row, "BirthDate")),
                "birth_place": "",
                "emergency_contact": "",
                "entry_semester": gradpro_semester_code(_first(info, "TermFirstEntered")),
                "entry_year": _term_year(_first(info, "TermFirstEntered")),
                "father_address": "",
                "father_name": "",
                "gender": _first(row, "Sex"),
                "last_enrolled_semester": gradpro_semester_code(
                    _first(info, "TermLastEnrolled")
                ),
                "last_school_attended": "",
                "marital_status": _first(row, "MaritalStatus"),
                "mother_address": "",
                "mother_name": "",
                "nationality": _first(info, "HomeCountry")
                or _first(row, "Citizenship", "Country"),
                "origin_county": _first(row, "RegionID"),
                "personal_email": _first(row, "EmailAddress"),
                "phone_no": _first(row, "Telephones"),
                "physical_address": _address(row),
                "username": _student_username(first, middle, last, seen_usernames),
            }
        )
    return rows


def merge_missing_grapro_students(
    primary_students: RowsT,
    grapro_students: RowsT,
    referenced_student_ids: set[str],
) -> tuple[RowsT, RowsT]:
    """Append GradePro students needed by historical grades and return report rows."""
    merged = list(primary_students)
    report_rows: RowsT = []
    seen_ids = {row.get("student_id", "") for row in primary_students}
    seen_usernames = {
        row.get("username", "") for row in primary_students if row.get("username", "")
    }
    for student in grapro_students:
        student_id = student.get("student_id", "")
        if student_id not in referenced_student_ids:
            continue
        action = "covered_by_primary"
        if student_id not in seen_ids:
            student = _student_with_unique_username(student, seen_usernames)
            merged.append(student)
            seen_ids.add(student_id)
            action = "added_missing"
        report_rows.append(
            {
                "action": action,
                "student_id": student_id,
                "student_name": student.get("long_name", ""),
                "legacy_curriculum": student.get("legacy_curriculum", ""),
                "source_name": student.get("source_name", ""),
                "source_path": student.get("source_path", ""),
            }
        )
    return merged, report_rows


def load_passthrough_rows(path: Path, source_name: str) -> RowsT:
    """Load rows intended to be copied to import-ready outputs."""
    rows: RowsT = []
    for row in read_rows(path):
        out = canonicalize_college_fields(row)
        out["source_name"] = source_name
        out["source_path"] = str(path)
        rows.append(out)
    return rows


def _grapro_student_info(grapro_dir: Path) -> dict[str, RowT]:
    """Return GradPro StudentInfo rows keyed by AccountID."""
    return {
        _first(row, "AccountID"): row
        for row in read_rows(grapro_dir / "StudentInfo.csv")
        if _first(row, "AccountID")
    }


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


def _student_username(
    first: str, middle: str, last: str, seen_usernames: set[str]
) -> str:
    """Return a deterministic unique username for a GradePro student."""
    username = mk_username(first, last, middle=middle, exclude=seen_usernames, sep=".")
    if not username:
        username = mk_username("student", last, exclude=seen_usernames, sep=".")
    seen_usernames.add(username)
    return username


def _student_with_unique_username(student: RowT, seen_usernames: set[str]) -> RowT:
    """Return a student row whose username is unique in the merged import set."""
    username = student.get("username", "")
    if username and username not in seen_usernames:
        seen_usernames.add(username)
        return student
    updated = dict(student)
    updated["username"] = _student_username(
        student.get("first_name", ""),
        student.get("middle_name", ""),
        student.get("last_name", student.get("student_id", "")),
        seen_usernames,
    )
    return updated


def _term_year(value: str) -> str:
    """Return the raw academic year portion of a GradPro term label."""
    academic_year, _ = gradpro_term_parts(value)
    return academic_year


def _address(row: RowT) -> str:
    """Join GradPro address fields into one physical-address string."""
    return ", ".join(
        value
        for value in (
            _first(row, "Address1"),
            _first(row, "Address2"),
            _first(row, "City"),
            _first(row, "State"),
            _first(row, "Country"),
        )
        if value
    )
