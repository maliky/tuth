"""Latest SmartSchool student extractor."""

from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

from app.people.utils import mk_username
from app.shared.source_truth.curriculum_match import (
    standardize_legacy_curriculum_label,
)
from app.shared.source_truth.io import RowT, read_rows
from app.shared.source_truth.smartschool_normalize import (
    clean_student_id,
    date_value,
    first_value,
    int_text,
    legacy_curriculum_from_row,
    name_from_parts,
    semester_code,
    semester_no,
)
from app.timetable.utils import normalize_academic_year

RowsT: TypeAlias = list[RowT]


def load_smartschool_students(smartschool_dir: Path, ok_tables: set[str]) -> RowsT:
    """Load latest SmartSchool students into the StudentResource shape."""
    if "UM_Students" not in ok_tables:
        return []
    path = smartschool_dir / "dbo_UM_Students.csv"
    last_terms = _student_last_terms(smartschool_dir, ok_tables)
    rows: RowsT = []
    seen_usernames: set[str] = set()
    for row in read_rows(path):
        student_id = clean_student_id(first_value(row, "StudentID"))
        if not student_id:
            continue
        first = first_value(row, "FirstName")
        middle = first_value(row, "MiddleName")
        last = first_value(row, "LastName") or student_id
        legacy_curriculum = legacy_curriculum_from_row(row)
        rows.append(
            {
                "source_name": "latest_smartschool",
                "source_path": str(path),
                "long_name": name_from_parts(first, middle, last),
                "first_name": first,
                "middle_name": middle,
                "last_name": last,
                "student_id": student_id,
                "curriculum": standardize_legacy_curriculum_label(legacy_curriculum),
                "legacy_curriculum": legacy_curriculum,
                "college_code": first_value(row, "College").upper(),
                "bio_Enrolled": first_value(row, "Enrolled"),
                "bio_EnrollmentType": first_value(row, "EnrollmentType"),
                "bio_admissionstatus": first_value(row, "AdmissionStatus"),
                "bio_scholarship": first_value(row, "Scholarship"),
                "birth_date": date_value(first_value(row, "DateOfBirth")),
                "birth_place": first_value(row, "PlaceOfBirth"),
                "emergency_contact": first_value(row, "EmergencyContact"),
                "entry_semester": semester_code(
                    first_value(row, "YearOfEntry"),
                    first_value(row, "SemesterOfEntry"),
                ),
                "entry_year": first_value(row, "YearOfEntry"),
                "father_address": first_value(row, "FatherAddress"),
                "father_name": first_value(row, "FatherName"),
                "gender": first_value(row, "Sex"),
                "last_enrolled_semester": last_terms.get(student_id, ""),
                "last_school_attended": first_value(row, "LastSchoolAttended"),
                "marital_status": first_value(row, "MaritalStatus"),
                "mother_address": first_value(row, "MotherAddress"),
                "mother_name": first_value(row, "MotherName"),
                "nationality": first_value(row, "Nationality"),
                "origin_county": first_value(row, "CountyOfOrigin"),
                "personal_email": first_value(row, "Email")
                or first_value(row, "AddressLine3"),
                "phone_no": first_value(row, "Phone") or first_value(row, "AddressLine2"),
                "physical_address": first_value(row, "AddressLine1"),
                "username": _student_username(first, middle, last, seen_usernames),
            }
        )
    return rows


def _student_last_terms(smartschool_dir: Path, ok_tables: set[str]) -> dict[str, str]:
    """Return each student's latest semester code from SmartSchool registrations."""
    terms: dict[str, tuple[int, int, str]] = {}
    if "UM_Registrations" not in ok_tables:
        return {}
    for row in read_rows(smartschool_dir / "dbo_UM_Registrations.csv"):
        student_id = clean_student_id(first_value(row, "StudentID"))
        academic_year = normalize_academic_year(first_value(row, "AcademicYear"))
        term_no = semester_no(first_value(row, "Semester"))
        if not student_id or not academic_year or not term_no:
            continue
        candidate = (
            _academic_year_start(academic_year),
            int(int_text(term_no)),
            semester_code(academic_year, term_no),
        )
        current = terms.get(student_id)
        if current is None or candidate[:2] > current[:2]:
            terms[student_id] = candidate
    return {student_id: term[2] for student_id, term in terms.items()}


def _student_username(
    first: str, middle: str, last: str, seen_usernames: set[str]
) -> str:
    """Return a deterministic unique username for one student import row."""
    username = mk_username(first, last, middle=middle, exclude=seen_usernames, sep=".")
    if not username:
        username = mk_username("student", last, exclude=seen_usernames, sep=".")
    seen_usernames.add(username)
    return username


def _academic_year_start(code: str) -> int:
    """Return a sortable start year from a normalized academic-year code."""
    try:
        return int(code.split("-", maxsplit=1)[0])
    except ValueError:
        return 0


__all__ = ["load_smartschool_students"]
