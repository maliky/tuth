"""Latest SmartSchool student extractor."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import TypeAlias

from app.people.utils import mk_username
from app.shared.source_truth.curriculum_match import (
    standardize_legacy_curriculum_label,
)
from app.shared.source_truth.college_codes import canonical_college_code
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
StudentCurriculumCountsT: TypeAlias = dict[str, Counter[str]]

STUDENT_COMPLETENESS_FIELDS = (
    "long_name",
    "first_name",
    "last_name",
    "legacy_curriculum",
    "college_code",
    "birth_date",
    "birth_place",
    "nationality",
    "origin_county",
    "personal_email",
    "phone_no",
    "physical_address",
)


def load_smartschool_students(smartschool_dir: Path, ok_tables: set[str]) -> RowsT:
    """Load latest SmartSchool students into the StudentResource shape."""
    if "UM_Students" not in ok_tables:
        return []
    path = smartschool_dir / "dbo_UM_Students.csv"
    last_terms = _student_last_terms(smartschool_dir, ok_tables)
    registration_curricula = _student_registration_curricula(smartschool_dir, ok_tables)
    rows: RowsT = []
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
                "college_code": canonical_college_code(first_value(row, "College")),
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
            }
        )
    return _with_unique_usernames(_dedupe_students_by_id(rows, registration_curricula))


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


def _student_registration_curricula(
    smartschool_dir: Path, ok_tables: set[str]
) -> StudentCurriculumCountsT:
    """Return legacy curriculum frequencies from operational registration rows."""
    counts: StudentCurriculumCountsT = {}
    if "UM_Registrations" not in ok_tables:
        return counts
    for row in read_rows(smartschool_dir / "dbo_UM_Registrations.csv"):
        student_id = clean_student_id(first_value(row, "StudentID"))
        legacy_curriculum = legacy_curriculum_from_row(row)
        if not student_id or not legacy_curriculum:
            continue
        counts.setdefault(student_id, Counter())[legacy_curriculum] += 1
    return counts


def _dedupe_students_by_id(
    rows: RowsT, registration_curricula: StudentCurriculumCountsT
) -> RowsT:
    """Keep one strongest SmartSchool student row for each student id."""
    selected: dict[str, RowT] = {}
    for row in rows:
        student_id = row.get("student_id", "")
        existing = selected.get(student_id)
        if existing is None or _student_row_score(
            row, registration_curricula
        ) > _student_row_score(existing, registration_curricula):
            selected[student_id] = row
    return list(selected.values())


def _student_row_score(
    row: RowT, registration_curricula: StudentCurriculumCountsT
) -> tuple[int, int, int]:
    """Score duplicate student rows by operational evidence and completeness."""
    student_id = row.get("student_id", "")
    legacy_curriculum = row.get("legacy_curriculum", "")
    registration_score = registration_curricula.get(student_id, Counter()).get(
        legacy_curriculum, 0
    )
    real_birth_date = int(row.get("birth_date", "") not in {"", "1900-01-01"})
    completeness = sum(1 for field in STUDENT_COMPLETENESS_FIELDS if row.get(field, ""))
    return (registration_score, real_birth_date, completeness)


def _with_unique_usernames(rows: RowsT) -> RowsT:
    """Populate deterministic unique usernames after duplicate student rows are removed."""
    seen_usernames: set[str] = set()
    output: RowsT = []
    for row in rows:
        updated = dict(row)
        updated["username"] = _student_username(
            row.get("first_name", ""),
            row.get("middle_name", ""),
            row.get("last_name", row.get("student_id", "")),
            seen_usernames,
        )
        output.append(updated)
    return output


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
