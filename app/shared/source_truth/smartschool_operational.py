"""SmartSchool operational row extractors for source-truth builds."""

from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

from app.shared.source_truth.curriculum_match import (
    standardize_legacy_curriculum_label,
)
from app.shared.source_truth.college_codes import canonical_college_code
from app.shared.source_truth.fuzzy import course_key
from app.shared.source_truth.io import RowT, read_rows
from app.shared.source_truth.smartschool_catalog import load_smartschool_course_lookup
from app.shared.source_truth.smartschool_normalize import (
    clean_student_id,
    course_identity_from_row,
    date_value,
    first_value,
    int_text,
    legacy_curriculum_from_row,
    semester_no,
)
from app.timetable.utils import normalize_academic_year

RowsT: TypeAlias = list[RowT]
RegistrationLookupT: TypeAlias = dict[tuple[str, str, str], RowT]
StudentLookupT: TypeAlias = dict[str, RowT]


def load_smartschool_grades(smartschool_dir: Path, ok_tables: set[str]) -> RowsT:
    """Load latest SmartSchool grade tables into the fast grade-import shape."""
    rows: RowsT = []
    registration_lookup = _registration_lookup(smartschool_dir, ok_tables)
    student_lookup = _student_lookup(smartschool_dir, ok_tables)
    course_lookup = load_smartschool_course_lookup(smartschool_dir)
    if "UM_Oldgrades" in ok_tables:
        rows.extend(
            _grade_rows_from_table(
                smartschool_dir / "dbo_UM_Oldgrades.csv",
                registration_lookup,
                student_lookup,
                course_lookup,
            )
        )
    if "UM_GradeSheet" in ok_tables:
        rows.extend(
            _grade_rows_from_table(
                smartschool_dir / "dbo_UM_GradeSheet.csv",
                registration_lookup,
                student_lookup,
                course_lookup,
            )
        )
    return rows


def load_smartschool_course_registrations(
    smartschool_dir: Path, ok_tables: set[str]
) -> RowsT:
    """Load SmartSchool course registrations from UM_StudentsCourses."""
    if "UM_StudentsCourses" not in ok_tables:
        return []
    path = smartschool_dir / "dbo_UM_StudentsCourses.csv"
    registration_lookup = _registration_lookup(smartschool_dir, ok_tables)
    student_lookup = _student_lookup(smartschool_dir, ok_tables)
    course_lookup = load_smartschool_course_lookup(smartschool_dir)
    rows: RowsT = []
    for row in read_rows(path):
        student_id = clean_student_id(first_value(row, "StudentID"))
        identity = course_identity_from_row(row)
        if not student_id or identity is None:
            continue
        dept = identity.department
        number = identity.number
        academic_year = first_value(row, "AcademicYear")
        term_no = semester_no(first_value(row, "Semester"))
        context = _student_term_context(
            student_id,
            academic_year,
            term_no,
            registration_lookup,
            student_lookup,
        )
        course = course_lookup.get(course_key(dept, number), {})
        rows.append(
            {
                "source_name": "latest_smartschool",
                "source_path": str(path),
                "student_id": student_id,
                "academic_year": academic_year,
                "semester_no": term_no,
                "course_dept": dept,
                "course_no": number,
                "section_no": int_text(first_value(row, "Section"), default="1"),
                "credit_hours": first_value(row, "CreditHours")
                or course.get("credit_hours", ""),
                "course_title": course.get("course_title", ""),
                "curriculum": context.get("curriculum", ""),
                "college_code": context.get("college_code", ""),
                "status": "pending",
            }
        )
    return rows


def load_smartschool_semester_enrollments(
    smartschool_dir: Path, ok_tables: set[str]
) -> RowsT:
    """Load UM_Registrations as semester-enrollment audit rows, not course rows."""
    if "UM_Registrations" not in ok_tables:
        return []
    path = smartschool_dir / "dbo_UM_Registrations.csv"
    rows: RowsT = []
    for row in read_rows(path):
        student_id = clean_student_id(first_value(row, "StudentID"))
        if not student_id:
            continue
        legacy_curriculum = legacy_curriculum_from_row(row)
        rows.append(
            {
                "source_name": "latest_smartschool",
                "source_path": str(path),
                "student_id": student_id,
                "academic_year": first_value(row, "AcademicYear"),
                "semester_no": semester_no(first_value(row, "Semester")),
                "registration_date": date_value(first_value(row, "Date")),
                "college_code": canonical_college_code(first_value(row, "College")),
                "major": first_value(row, "Major"),
                "enrollment_type": first_value(row, "EnrollmentType"),
                "curriculum": standardize_legacy_curriculum_label(legacy_curriculum),
                "scholarship": first_value(row, "Scholarship"),
                "reference": first_value(row, "Reference"),
                "sysref": first_value(row, "SysRef"),
                "cleared": first_value(row, "Cleared"),
                "grades_uploaded": first_value(row, "GradesUploaded"),
            }
        )
    return rows


def _grade_rows_from_table(
    path: Path,
    registration_lookup: RegistrationLookupT,
    student_lookup: StudentLookupT,
    course_lookup: dict[str, RowT],
) -> RowsT:
    """Normalize one SmartSchool grade table."""
    rows: RowsT = []
    for row in read_rows(path):
        student_id = clean_student_id(first_value(row, "StudentID"))
        identity = course_identity_from_row(row)
        grade_code = first_value(row, "Grade")
        if not student_id or identity is None or not grade_code:
            continue
        dept = identity.department
        number = identity.number
        academic_year = first_value(row, "AcademicYear")
        term_no = semester_no(first_value(row, "Semester"))
        context = _student_term_context(
            student_id,
            academic_year,
            term_no,
            registration_lookup,
            student_lookup,
        )
        course = course_lookup.get(course_key(dept, number), {})
        rows.append(
            {
                "source_name": "latest_smartschool",
                "source_path": str(path),
                "academic_year": academic_year,
                "semester_no": term_no,
                "student_id": student_id,
                "course_dept": dept,
                "course_no": number,
                "section_no": int_text(first_value(row, "Section"), default="1"),
                "grade_code": grade_code,
                "credit_hours": first_value(row, "CrHrs")
                or course.get("credit_hours", ""),
                "curriculum": context.get("curriculum", ""),
                "college_code": context.get("college_code", ""),
                "course_title": first_value(row, "Description")
                or course.get("course_title", ""),
            }
        )
    return rows


def _registration_lookup(
    smartschool_dir: Path, ok_tables: set[str]
) -> RegistrationLookupT:
    """Return semester registration context by student/year/semester."""
    if "UM_Registrations" not in ok_tables:
        return {}
    rows: RegistrationLookupT = {}
    for row in read_rows(smartschool_dir / "dbo_UM_Registrations.csv"):
        student_id = clean_student_id(first_value(row, "StudentID"))
        academic_year = first_value(row, "AcademicYear")
        term_no = semester_no(first_value(row, "Semester"))
        if not student_id or not academic_year or not term_no:
            continue
        legacy_curriculum = legacy_curriculum_from_row(row)
        rows[(student_id, normalize_academic_year(academic_year), term_no)] = {
            "curriculum": standardize_legacy_curriculum_label(legacy_curriculum),
            "college_code": canonical_college_code(first_value(row, "College")),
        }
    return rows


def _student_lookup(smartschool_dir: Path, ok_tables: set[str]) -> StudentLookupT:
    """Return fallback student context by student id."""
    if "UM_Students" not in ok_tables:
        return {}
    rows: StudentLookupT = {}
    for row in read_rows(smartschool_dir / "dbo_UM_Students.csv"):
        student_id = clean_student_id(first_value(row, "StudentID"))
        if not student_id:
            continue
        legacy_curriculum = legacy_curriculum_from_row(row)
        rows[student_id] = {
            "curriculum": standardize_legacy_curriculum_label(legacy_curriculum),
            "college_code": canonical_college_code(first_value(row, "College")),
        }
    return rows


def _student_term_context(
    student_id: str,
    academic_year: str,
    semester_no: str,
    registration_lookup: RegistrationLookupT,
    student_lookup: StudentLookupT,
) -> RowT:
    """Return curriculum/college context for one student term."""
    key = (student_id, normalize_academic_year(academic_year), semester_no)
    context = registration_lookup.get(key) or student_lookup.get(student_id) or {}
    return {
        "curriculum": context.get("curriculum", "") or "Legacy",
        "college_code": context.get("college_code", ""),
    }


__all__ = [
    "load_smartschool_course_registrations",
    "load_smartschool_grades",
    "load_smartschool_semester_enrollments",
]
