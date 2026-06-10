"""Audit helpers for malformed SmartSchool course identities."""

from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

from app.shared.course_wrangling import (
    compact_course_code,
    invalid_course_identity_reason,
    normalize_course_number,
    parse_course_identity_result,
)
from app.shared.source_truth.io import RowT, read_rows
from app.shared.source_truth.smartschool_normalize import first_value

RowsT: TypeAlias = list[RowT]
CourseTableSpecT: TypeAlias = tuple[str, str]

COURSE_IDENTITY_TABLES: tuple[CourseTableSpecT, ...] = (
    ("UM_CoursesLevels", "dbo_UM_CoursesLevels.csv"),
    ("UM_CurriculumCourses", "dbo_UM_CurriculumCourses.csv"),
    ("UM_StudentsCourses", "dbo_UM_StudentsCourses.csv"),
    ("UM_GradeSheet", "dbo_UM_GradeSheet.csv"),
    ("UM_Oldgrades", "dbo_UM_Oldgrades.csv"),
)


def load_invalid_smartschool_course_identities(
    smartschool_dir: Path, ok_tables: set[str]
) -> RowsT:
    """Return SmartSchool course rows that cannot be safely imported."""
    rows: RowsT = []
    for table_name, filename in COURSE_IDENTITY_TABLES:
        if table_name not in ok_tables:
            continue
        path = smartschool_dir / filename
        for row_number, row in enumerate(read_rows(path), start=2):
            raw_dept = first_value(row, "CourseCode")
            raw_number = first_value(row, "CourseNo")
            if not raw_dept and not raw_number:
                continue
            if parse_course_identity_result(raw_dept, raw_number) is not None:
                continue
            rows.append(
                {
                    "source_name": "latest_smartschool",
                    "source_path": str(path),
                    "table_name": table_name,
                    "row_number": str(row_number),
                    "raw_course_dept": raw_dept,
                    "raw_course_no": raw_number,
                    "normalized_dept_attempt": compact_course_code(raw_dept),
                    "normalized_no_attempt": normalize_course_number(raw_number),
                    "reason": invalid_course_identity_reason(raw_dept, raw_number),
                }
            )
    return rows


def load_repaired_smartschool_course_identities(
    smartschool_dir: Path, ok_tables: set[str]
) -> RowsT:
    """Return parseable SmartSchool course rows that required normalization."""
    rows: RowsT = []
    for table_name, filename in COURSE_IDENTITY_TABLES:
        if table_name not in ok_tables:
            continue
        path = smartschool_dir / filename
        for row_number, row in enumerate(read_rows(path), start=2):
            raw_dept = first_value(row, "CourseCode")
            raw_number = first_value(row, "CourseNo")
            if not raw_dept and not raw_number:
                continue
            parsed = parse_course_identity_result(raw_dept, raw_number)
            if parsed is None:
                continue
            if parsed.source == "direct_canonical" and not parsed.repair_reason:
                continue
            rows.append(
                {
                    "source_name": "latest_smartschool",
                    "source_path": str(path),
                    "table_name": table_name,
                    "row_number": str(row_number),
                    "raw_course_dept": raw_dept,
                    "raw_course_no": raw_number,
                    "course_dept": parsed.department,
                    "course_no": parsed.number,
                    "parse_source": parsed.source,
                    "repair_reason": parsed.repair_reason,
                }
            )
    return rows
