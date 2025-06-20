"""General utility helpers shared between apps."""

from typing import Mapping, Optional, Tuple

from app.academics.constants import COURSE_PATTERN
from app.academics.models.department import Department

def expand_course_code(
    code: str, *, row: Optional[Mapping[str, str]] = None, default_college: str = "COAS"
) -> Tuple[str, str, str]:
    """Parse a course code into its components.

    Parameters
    ----------
    code : str
        Raw course code such as "AGR121-CFAS".
    row : Mapping[str, str] | None, optional
        Optional CSV row providing a college_code fallback. The
        college_code value is used only when the course code itself
        does not include a college segment.
    default_college : str, optional
        College code to use when none is provided. Defaults to "COAS".

    Returns
    -------
    tuple[str, str, str]
        The department code, course number and college code.
    """

    assert "/" not in code

    match = COURSE_PATTERN.search(code.strip().upper())
    assert match is not None, f"Code '{code}' doesn't match expected pattern"

    college, dept, num = (
        match.group("college"),
        match.group("dept"),
        match.group("num"),
    )

    if not college:
        if row and "college_code" in row:
            college = row["college_code"]
        else:
            college = default_college

    return college, dept, num


def make_course_code(dept: Department, number: str) -> str:
    """Return a compact code from a department, number and optional college.

    Returns:  A normalized course identifier.
    """
    college_code = dept.college.code
    return f"{dept.short_name}{number}{college_code}".upper()
