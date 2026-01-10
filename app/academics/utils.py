"""Utility function related to academics objects."""

from typing import TYPE_CHECKING, Mapping, Optional, Tuple

from app.academics.constants import COURSE_PATTERN  # safe
from app.academics.models.college import College
from app.shared.types import Row
from app.shared.utils import get_in_row

if TYPE_CHECKING:
    from app.academics.models.department import Department


def expand_course_code(
    code: str, *, row: Optional[Mapping[str, str]] = None
) -> Tuple[str, str, str]:
    """Parse a course code into its components.

    Args:
        code: Raw course code in the pattern <college_code>-<dept_code><course_no>.
        row: Row data used to supply a college_code when the code omits it.

    Returns:
        Three values: college_code, dept_shortname, course_no.

    Examples:
        >>> expand_course_code("CAFS-AGR121")
        ("CAFS", "AGR", "121")
        >>> expand_course_code("AGR121", row={"college_code": "CAFS"})
        ("CAFS", "AGR", "121")
    """
    assert "/" not in code

    _match = COURSE_PATTERN.search(code.strip().upper())
    assert _match is not None, f"Code '{code}' doesn't match expected pattern"

    college_code, dept_shortname, course_no = (
        _match.group("college"),
        _match.group("dept"),
        _match.group("num"),
    )

    if not college_code:
        if row and "college_code" in row:
            college_code = row["college_code"]
        else:
            college_code = College.get_default().code

    return college_code, dept_shortname, course_no


def make_course_code(dept: "Department", number: str, short=False) -> str:
    """Build a course code from a department and a course number.

    Args:
        dept: Record providing the department code or shortname.
        number: Course number segment to append.
        short: Use the department code without the college segment.

    Returns:
        An upper-cased course code string.

    Examples:
        If dept.shortname is "AGR" and number is "121",
        the result is "AGR-121".
    """
    _dept_rep = dept.code if short else dept.shortname
    return f"{_dept_rep}-{number}".upper()
