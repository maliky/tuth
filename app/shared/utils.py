"""Utils module."""

from typing import Mapping, Optional, Tuple

from app.shared.constants import COURSE_PATTERN

# r"(?P<dept>[A-Z]{2,4})[_-]?(?P<num>[0-9]{3})(?:\s*-\s*(?P<college>[A-Z]{3,4}))?"


def expand_course_code(
    code: str, *, row: Optional[Mapping[str, str]] = None, default_college: str = "COAS"
) -> Tuple[str, str, str]:
    """Return (dept_code, course_num, college_code) from ``code``.

    ``code`` may optionally include the college after a dash.  If missing,
    ``row['college']`` is used when available, otherwise ``default_college``.
    ``row`` is the raw CSV row passed during imports.
    """

    assert "/" not in code

    match = COURSE_PATTERN.search(code.strip().upper())
    assert match is not None, f"Code '{code}' doesn't match expected pattern"

    dept, num, college = match.group("dept"), match.group("num"), match.group("college")
    if row and "college" in row:
        college = row["college"]
    else:
        college = default_college

    return dept, num, college


def make_course_code(name: str, number: str, college: str | None = None) -> str:
    """Compact representation used internally to identify a course."""
    cc = "" if college is None else f"-{college}"
    return f"{name}{number}{cc}".upper()
