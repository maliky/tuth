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
    """Return a course code.  dept.shortname+course.num.

    if short == True use dept.code (without college info)
    """
    _dept_rep = dept.code if short else dept.shortname
    return f"{_dept_rep}-{number}".upper()
