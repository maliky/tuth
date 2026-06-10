"""GradPro operational extractors for historical source-truth rows."""

from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

from app.registry.constants import GRADES_NUM
from app.shared.source_truth.fuzzy import course_key, split_course_code
from app.shared.source_truth.grapro_normalize import gradpro_term_parts
from app.shared.source_truth.io import RowT, read_rows
from app.shared.source_truth.smartschool_normalize import (
    clean_student_id,
    first_value,
    int_text,
)

RowsT: TypeAlias = list[RowT]
GradeLoadResultT: TypeAlias = tuple[RowsT, RowsT]

VALID_GRADE_CODES = {code.upper() for code in GRADES_NUM}
VALID_GRADE_CODES.add("AB")


def load_grapro_grades(grapro_dir: Path) -> GradeLoadResultT:
    """Load GradPro StudentRecords into the fast grade-import shape."""
    path = grapro_dir / "StudentRecords.csv"
    course_lookup = _course_lookup(grapro_dir)
    rows: RowsT = []
    skipped: RowsT = []
    for row_number, row in enumerate(read_rows(path), start=1):
        parsed = _grade_row(path, row_number, row, course_lookup)
        if parsed.get("reason"):
            skipped.append(parsed)
        else:
            rows.append(parsed)
    return rows, skipped


def _grade_row(
    path: Path,
    row_number: int,
    row: RowT,
    course_lookup: dict[str, RowT],
) -> RowT:
    """Return one import row or one skipped-row report."""
    student_id = clean_student_id(first_value(row, "AccountID"))
    grade_code = first_value(row, "FinalGrade").upper()
    academic_year, semester_no = gradpro_term_parts(first_value(row, "TermID"))
    dept, number = split_course_code(first_value(row, "ItemID"))
    if not grade_code:
        return _skip_row(path, row_number, row, "missing_grade")
    if grade_code not in VALID_GRADE_CODES:
        return _skip_row(path, row_number, row, "unsupported_grade_code")
    if not student_id:
        return _skip_row(path, row_number, row, "missing_student_id")
    if not academic_year or not semester_no:
        return _skip_row(path, row_number, row, "invalid_term")
    if not dept or not number:
        return _skip_row(path, row_number, row, "invalid_course_identity")

    course = course_lookup.get(course_key(dept, number), {})
    return {
        "source_name": "grapro_legacy",
        "source_path": str(path),
        "source_row_number": str(row_number),
        "academic_year": academic_year,
        "semester_no": semester_no,
        "student_id": student_id,
        "course_dept": dept,
        "course_no": number,
        "section_no": int_text(first_value(row, "SectionID"), default="1"),
        "grade_code": grade_code,
        "credit_hours": first_value(row, "Quantity") or course.get("credit_hours", ""),
        "curriculum": first_value(row, "ProgramID") or "Legacy",
        "college_code": course.get("college_code", ""),
        "course_title": first_value(row, "Description") or course.get("course_title", ""),
    }


def _course_lookup(grapro_dir: Path) -> dict[str, RowT]:
    """Return GradPro course metadata keyed by normalized course identity."""
    rows: dict[str, RowT] = {}
    for row in read_rows(grapro_dir / "Courses.csv"):
        dept, number = split_course_code(first_value(row, "CourseID", "ItemID"))
        key = course_key(dept, number)
        if not key:
            continue
        rows[key] = {
            "course_title": first_value(row, "CourseName", "CourseDescription"),
            "credit_hours": first_value(row, "CreditHours"),
            "college_code": "",
        }
    return rows


def _skip_row(path: Path, row_number: int, row: RowT, reason: str) -> RowT:
    """Build one skipped GradPro grade report row."""
    return {
        "source_name": "grapro_legacy",
        "source_path": str(path),
        "row_number": str(row_number),
        "student_id": first_value(row, "AccountID"),
        "term_id": first_value(row, "TermID"),
        "item_id": first_value(row, "ItemID"),
        "grade_code": first_value(row, "FinalGrade"),
        "reason": reason,
    }


__all__ = ["load_grapro_grades"]
