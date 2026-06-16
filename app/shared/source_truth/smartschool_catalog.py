"""Latest SmartSchool catalog extractors for source-truth builds."""

from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

from app.shared.source_truth.curriculum_match import (
    standardize_legacy_curriculum_label,
)
from app.shared.source_truth.college_codes import canonical_college_code
from app.shared.source_truth.fuzzy import course_key
from app.shared.source_truth.io import RowT, read_rows
from app.shared.source_truth.smartschool_normalize import (
    course_identity_from_row,
    first_value,
)

RowsT: TypeAlias = list[RowT]


def load_smartschool_courses(smartschool_dir: Path, ok_tables: set[str]) -> RowsT:
    """Load latest SmartSchool courses only when required exports passed integrity."""
    required = {"UM_Courses", "UM_CoursesLevels"}
    if not required.issubset(ok_tables):
        return []
    courses_path = smartschool_dir / "dbo_UM_Courses.csv"
    levels_path = smartschool_dir / "dbo_UM_CoursesLevels.csv"
    titles = {
        first_value(row, "CourseCode").upper(): first_value(row, "Course")
        for row in read_rows(courses_path)
        if first_value(row, "CourseCode")
    }
    rows: RowsT = []
    for row in read_rows(levels_path):
        identity = course_identity_from_row(row)
        if identity is None:
            continue
        dept = identity.department
        number = identity.number
        rows.append(
            {
                "source_name": "latest_smartschool",
                "source_path": str(levels_path),
                "row_key": f"latest_smartschool:{course_key(dept, number)}",
                "course_key": course_key(dept, number),
                "course_dept": dept,
                "course_no": number,
                "course_title": first_value(row, "Description") or titles.get(dept, ""),
                "credit_hours": first_value(row, "CreditHours"),
                "college_code": "",
                "description": "",
            }
        )
    return rows


def load_smartschool_curricula(smartschool_dir: Path, ok_tables: set[str]) -> RowsT:
    """Load latest SmartSchool curriculum/program labels as historical witnesses."""
    rows_by_key: dict[str, RowT] = {}
    if "UM_Curriculums" in ok_tables:
        path = smartschool_dir / "dbo_UM_Curriculums.csv"
        for row in read_rows(path):
            _add_curriculum_row(rows_by_key, path, first_value(row, "Curriculum"), "", "")
    if "UM_Programs" in ok_tables:
        path = smartschool_dir / "dbo_UM_Programs.csv"
        for row in read_rows(path):
            _add_curriculum_row(
                rows_by_key,
                path,
                first_value(row, "ProgramID"),
                first_value(row, "Description"),
                "",
            )
    if "UM_Students" in ok_tables:
        path = smartschool_dir / "dbo_UM_Students.csv"
        for row in read_rows(path):
            college = first_value(row, "College")
            for label in (
                first_value(row, "Major"),
                first_value(row, "Curriculum"),
                first_value(row, "ProgramID"),
            ):
                _add_curriculum_row(rows_by_key, path, label, "", college)
    if "UM_Registrations" in ok_tables:
        path = smartschool_dir / "dbo_UM_Registrations.csv"
        for row in read_rows(path):
            college = first_value(row, "College")
            for label in (first_value(row, "Major"), first_value(row, "EnrollmentType")):
                _add_curriculum_row(rows_by_key, path, label, "", college)
    return list(rows_by_key.values())


def load_smartschool_curriculum_courses(
    smartschool_dir: Path, ok_tables: set[str]
) -> RowsT:
    """Load latest SmartSchool curriculum-course rows as historical witnesses."""
    required = {"UM_CurriculumCourses", "UM_CoursesLevels"}
    if not required.issubset(ok_tables):
        return []
    path = smartschool_dir / "dbo_UM_CurriculumCourses.csv"
    course_lookup = load_smartschool_course_lookup(smartschool_dir)
    rows: RowsT = []
    for row in read_rows(path):
        identity = course_identity_from_row(row)
        curriculum = standardize_legacy_curriculum_label(first_value(row, "Curriculum"))
        if not curriculum or identity is None:
            continue
        dept = identity.department
        number = identity.number
        course = course_lookup.get(course_key(dept, number), {})
        year_number, term_number = _curriculum_year_term(first_value(row, "Semester"))
        rows.append(
            {
                "source_name": "latest_smartschool",
                "source_path": str(path),
                "curriculum": curriculum,
                "course_dept": dept,
                "course_no": number,
                "course_title": course.get("course_title", ""),
                "credit_hours": course.get("credit_hours", ""),
                "college_code": "",
                "year_number": year_number,
                "semester_number": term_number,
                "level_number": year_number,
                "required_group_number": "0",
                "min_validated_credits": "0",
                "is_required": "true",
            }
        )
    return rows


def load_smartschool_course_lookup(smartschool_dir: Path) -> dict[str, RowT]:
    """Return latest SmartSchool course title/credit lookup by course key."""
    rows: dict[str, RowT] = {}
    for row in read_rows(smartschool_dir / "dbo_UM_CoursesLevels.csv"):
        identity = course_identity_from_row(row)
        if identity is None:
            continue
        dept = identity.department
        number = identity.number
        key = course_key(dept, number)
        if not key:
            continue
        rows[key] = {
            "course_title": first_value(row, "Description"),
            "credit_hours": first_value(row, "CreditHours"),
        }
    return rows


def _add_curriculum_row(
    rows_by_key: dict[str, RowT],
    source_path: Path,
    raw_label: str,
    long_name: str,
    college: str,
) -> None:
    """Add one normalized historical curriculum row when it is meaningful."""
    label = standardize_legacy_curriculum_label(raw_label)
    key = _compact(label)
    if not label or not key or key in rows_by_key:
        return
    rows_by_key[key] = {
        "source_name": "latest_smartschool",
        "source_path": str(source_path),
        "curriculum": label,
        "curriculum_key": key,
        "long_name": long_name or label,
        "college_code": canonical_college_code(college),
        "status": "historical",
        "is_active": "false",
    }


def _curriculum_year_term(raw_semester: str) -> tuple[str, str]:
    """Convert SmartSchool curriculum semester slots into year/term values."""
    try:
        number = int(float(raw_semester or "0"))
    except ValueError:
        return "99", "0"
    if number <= 0:
        return "99", "0"
    return str(((number - 1) // 2) + 1), str(1 if number % 2 else 2)


def _compact(value: str) -> str:
    """Return a compact comparison key."""
    return "".join(ch for ch in value.upper() if ch.isalnum())


__all__ = [
    "load_smartschool_course_lookup",
    "load_smartschool_courses",
    "load_smartschool_curricula",
    "load_smartschool_curriculum_courses",
]
