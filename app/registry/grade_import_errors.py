"""Error logging helpers for grade import commands."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Mapping, TypeAlias

from app.shared.utils import get_in_row

RowT: TypeAlias = Mapping[str, str]


def write_grade_error_log(rows: list[tuple[int, str, RowT]]) -> Path:
    """Write compact grade import errors for importer repair."""
    log_path = Path("logs/import_errors/import_grades_errors.csv")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "row_number",
        "error",
        "student_id",
        "academic_year",
        "semester_no",
        "course_dept",
        "course_no",
        "section_no",
        "grade_code",
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
                    "course_dept": get_in_row("course_dept", row),
                    "course_no": get_in_row("course_no", row),
                    "section_no": get_in_row("section_no", row),
                    "grade_code": get_in_row("grade_code", row),
                }
            )
    return log_path


__all__ = ["write_grade_error_log"]
