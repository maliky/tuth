"""General utility helpers shared between apps."""

from typing import Mapping, Optional, Tuple

from app.academics.constants import COURSE_PATTERN
from app.academics.models.college import College
from app.academics.models.department import Department


def expand_course_code(
    code: str, *, row: Optional[Mapping[str, str]] = None
) -> Tuple[str, str, str]:
    """Parse a course code into its components.

    Parameters
    ----------
    code : Raw course code such as "CAFS-AGR121".
        <college_code>-<dept_code><course_no>
        See COURSE_PATTERN.
    row : Optional CSV row providing a college_code fallback. The
        college_code value is used only when the course code itself
        does not include a college segment.

    Returns
    -------
    tuple[str, str, str]
        The department code, course number and college code.
    """
    assert "/" not in code

    _match = COURSE_PATTERN.search(code.strip().upper())
    assert _match is not None, f"Code '{code}' doesn't match expected pattern"

    college_code, dept_short_name, course_no = (
        _match.group("college"),
        _match.group("dept"),
        _match.group("num"),
    )

    if not college_code:
        if row and "college_code" in row:
            college_code = row["college_code"]
        else:
            college_code = College.get_default().code

    return college_code, dept_short_name, course_no


def make_course_code(dept: Department, number: str, short=False) -> str:
    """Return a course code.

    formed from dept.code+course.num
    if short == True use dept.short_name (without college info)
    """
    _dept_code = dept.short_name if short else dept.code
    return f"{_dept_code}-{number}".upper()


def get_in_row(key: str, row: Optional[dict[str, str | None]]) -> str:
    """Return a value from the row which is a dict of str and optional None.

    Does so safely always returning something even if None is in the row.
    """
    return ((row or {}).get(key) or "").strip()


def as_title(value: str) -> str:
    """Utility to clean a strip _ from a str and capitalize its words."""
    return value.replace("_", " ").title()


def clean_column_headers(dataset):
    """Strip blank headers that may appear due to trailing commas and remap column names."""
    # sanitize column headers: strip whitespace
    sanitised = [(header or "").strip() for header in dataset.headers]
    rename_map = {
        "course_dept_no": "course_dept",
        "course_name": "course_dept",
        "dept_code": "course_dept",
        "Instructor": "faculty",
        "semester": "semester_no",
    }
    dataset.headers = [rename_map.get(name, name) for name in sanitised]
    return dataset
