"""Extract normalized witnesses from SmartSchool, GradPro, and TUCurricula."""

from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

from app.shared.source_truth.fuzzy import course_key, split_course_code
from app.shared.source_truth.io import RowT, read_rows

RowsT: TypeAlias = list[RowT]


def load_tucurricula_courses(import_dir: Path) -> RowsT:
    """Load revised curriculum course catalog witnesses."""
    path = import_dir / "academic_course.tsv"
    rows: RowsT = []
    for row in read_rows(path):
        rows.append(
            _course_row(
                source_name="tucurricula",
                source_path=path,
                dept=_first(row, "course_dept"),
                number=_first(row, "course_no"),
                title=_first(row, "course_title"),
                credit=_first(row, "credit_hours"),
                college=_first(row, "college_code", "course_college_code"),
                description=_first(row, "description"),
            )
        )
    return rows


def load_tucurricula_curricula(import_dir: Path) -> RowsT:
    """Load revised curriculum witnesses."""
    path = import_dir / "academic_curriculum.tsv"
    rows: RowsT = []
    for row in read_rows(path):
        curriculum = _first(row, "curriculum")
        rows.append(
            {
                "source_name": "tucurricula",
                "source_path": str(path),
                "curriculum": curriculum,
                "curriculum_key": _compact(curriculum),
                "long_name": _first(row, "long_name"),
                "college_code": _first(row, "college_code", "curriculum_college_code"),
                "status": "approved",
                "is_active": "true",
            }
        )
    return rows


def load_tucurricula_curriculum_courses(import_dir: Path) -> RowsT:
    """Load revised curriculum-course witnesses."""
    path = import_dir / "academic_curriculum_course.tsv"
    rows: RowsT = []
    for row in read_rows(path):
        rows.append(
            {
                "source_name": "tucurricula",
                "source_path": str(path),
                "curriculum": _first(row, "curriculum"),
                "course_dept": _first(row, "course_dept"),
                "course_no": _first(row, "course_no"),
                "course_title": _first(row, "course_title"),
                "credit_hours": _first(row, "credit_hours"),
                "college_code": _first(row, "college_code"),
                "year_number": _first(row, "year_number"),
                "semester_number": _first(row, "semester_number"),
                "level_number": _first(row, "level_number"),
                "required_group_number": _first(row, "required_group_number") or "0",
                "min_validated_credits": _first(row, "min_validated_credits") or "0",
                "is_required": _first(row, "is_required"),
            }
        )
    return rows


def load_tucurricula_requirements(import_dir: Path) -> RowsT:
    """Load revised curriculum prerequisite/corequisite import rows."""
    path = import_dir / "academic_curriculum_requirement.tsv"
    rows: RowsT = []
    for row in read_rows(path):
        out = dict(row)
        out["source_name"] = "tucurricula"
        out["source_path"] = str(path)
        rows.append(out)
    return rows


def load_fundamental_courses(fundamentals_dir: Path) -> RowsT:
    """Load import-ready historical SmartSchool course witnesses."""
    path = fundamentals_dir / "academic_course.csv"
    rows: RowsT = []
    for row in read_rows(path):
        rows.append(
            _course_row(
                source_name="fundamentals_smartschool",
                source_path=path,
                dept=_first(row, "course_dept"),
                number=_first(row, "course_no"),
                title=_first(row, "course_title"),
                credit=_first(row, "credit_hours"),
                college=_first(row, "college_code"),
            )
        )
    return rows


def load_fundamental_curricula(fundamentals_dir: Path) -> RowsT:
    """Load historical SmartSchool curriculum labels."""
    path = fundamentals_dir / "academics_curriculums.csv"
    rows: RowsT = []
    for row in read_rows(path):
        curriculum = _first(row, "EnrollmentType", "curriculum")
        rows.append(
            {
                "source_name": "fundamentals_smartschool",
                "source_path": str(path),
                "curriculum": curriculum,
                "curriculum_key": _compact(curriculum),
                "long_name": curriculum,
                "college_code": "",
                "status": "historical",
            }
        )
    return rows


def load_fundamental_curriculum_courses(fundamentals_dir: Path) -> RowsT:
    """Load historical SmartSchool curriculum-course witnesses."""
    path = fundamentals_dir / "academic_curriculum_course.csv"
    rows: RowsT = []
    for row in read_rows(path):
        rows.append(
            {
                "source_name": "fundamentals_smartschool",
                "source_path": str(path),
                "curriculum": _first(row, "curriculum"),
                "course_dept": _first(row, "course_dept"),
                "course_no": _first(row, "course_no"),
                "course_title": "",
                "credit_hours": _first(row, "credit_hours"),
                "college_code": _first(row, "college_code"),
                "year_number": "99",
                "semester_number": "0",
                "level_number": "99",
                "required_group_number": "0",
                "min_validated_credits": "0",
                "is_required": "",
            }
        )
    return rows


def load_grapro_courses(grapro_dir: Path) -> RowsT:
    """Load GradPro course catalog witnesses."""
    path = grapro_dir / "Courses.csv"
    rows: RowsT = []
    for row in read_rows(path):
        dept, number = split_course_code(_first(row, "CourseID", "ItemID"))
        rows.append(
            _course_row(
                source_name="grapro_legacy",
                source_path=path,
                dept=dept or _first(row, "AreaID"),
                number=number,
                title=_first(row, "CourseName", "CourseDescription"),
                credit=_first(row, "CreditHours"),
                college="",
                description=_first(row, "CourseDescription"),
            )
        )
    return rows


def _course_row(
    *,
    source_name: str,
    source_path: Path,
    dept: str,
    number: str,
    title: str,
    credit: str,
    college: str,
    description: str = "",
) -> RowT:
    """Build one normalized course witness row."""
    key = course_key(dept, number)
    return {
        "source_name": source_name,
        "source_path": str(source_path),
        "row_key": f"{source_name}:{key}:{title}",
        "course_key": key,
        "course_dept": dept.upper(),
        "course_no": number.upper(),
        "course_title": title,
        "credit_hours": credit,
        "college_code": college.upper(),
        "description": description,
    }


def _first(row: RowT, *keys: str) -> str:
    """Return the first non-empty value from row by candidate column name."""
    for key in keys:
        value = row.get(key, "")
        if value:
            return value.strip()
    return ""


def _compact(value: str) -> str:
    """Return a compact comparison key."""
    return "".join(ch for ch in value.upper() if ch.isalnum())
