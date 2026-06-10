"""Merge grade witnesses with SmartSchool precedence."""

from __future__ import annotations

from typing import TypeAlias

from app.shared.source_truth.fuzzy import course_key
from app.shared.source_truth.io import RowT
from app.timetable.utils import normalize_academic_year

RowsT: TypeAlias = list[RowT]
MergeResultT: TypeAlias = tuple[RowsT, RowsT]


def merge_missing_grades(primary_rows: RowsT, supplement_rows: RowsT) -> MergeResultT:
    """Return primary grades plus supplement rows missing from primary."""
    merged: RowsT = list(primary_rows)
    report_rows: RowsT = []
    primary_keys = {_grade_key(row) for row in primary_rows if _grade_key(row)}
    seen = set(primary_keys)
    for row in supplement_rows:
        key = _grade_key(row)
        if not key:
            report_rows.append(_report_row(row, key, "skipped_unkeyed"))
            continue
        if key in seen:
            action = "duplicate_with_primary" if key in primary_keys else "duplicate"
            report_rows.append(_report_row(row, key, action))
            continue
        merged.append(row)
        seen.add(key)
        report_rows.append(_report_row(row, key, "added_missing"))
    return merged, report_rows


def _grade_key(row: RowT) -> str:
    """Return the import identity for one grade row."""
    student_id = row.get("student_id", "").strip()
    academic_year = normalize_academic_year(row.get("academic_year", ""))
    semester_no = row.get("semester_no", "").strip()
    course = course_key(row.get("course_dept"), row.get("course_no"))
    section_no = row.get("section_no", "").strip() or "1"
    if not all((student_id, academic_year, semester_no, course, section_no)):
        return ""
    return "|".join((student_id, academic_year, semester_no, course, section_no))


def _report_row(row: RowT, key: str, action: str) -> RowT:
    """Build one merge action report row."""
    return {
        "action": action,
        "grade_key": key,
        "student_id": row.get("student_id", ""),
        "academic_year": row.get("academic_year", ""),
        "semester_no": row.get("semester_no", ""),
        "course_dept": row.get("course_dept", ""),
        "course_no": row.get("course_no", ""),
        "section_no": row.get("section_no", ""),
        "grade_code": row.get("grade_code", ""),
        "source_name": row.get("source_name", ""),
        "source_path": row.get("source_path", ""),
        "source_row_number": row.get("source_row_number", ""),
    }


__all__ = ["merge_missing_grades"]
