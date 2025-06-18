"""General utility helpers shared between apps."""

from typing import Mapping, Optional, Tuple

from app.shared.constants import COURSE_PATTERN

# r"(?P<dept>[A-Z]{2,4})[_-]?(?P<num>[0-9]{3})(?:\s*-\s*(?P<college>[A-Z]{3,4}))?"


def expand_course_code(
    code: str, *, row: Optional[Mapping[str, str]] = None, default_college: str = "COAS"
) -> Tuple[str, str, str]:
    """Parse a course code into its components.

    Parameters
    ----------
    code : str
        Raw course code such as ``"AGR121-CFAS"``.
    row : Mapping[str, str] | None, optional
        Optional CSV row providing a ``college_code`` fallback. The
        ``college_code`` value is used only when the course code itself
        does not include a college segment.
    default_college : str, optional
        College code to use when none is provided. Defaults to ``"COAS"``.

    Returns
    -------
    tuple[str, str, str]
        The department code, course number and college code.
    """

    assert "/" not in code

    match = COURSE_PATTERN.search(code.strip().upper())
    assert match is not None, f"Code '{code}' doesn't match expected pattern"

    dept, num, college = (
        match.group("dept"),
        match.group("num"),
        match.group("college"),
    )

    if not college:
        if row and "college_code" in row:
            college = row["college_code"]
        else:
            college = default_college

    return dept, num, college


def make_course_code(name: str, number: str, college: str | None = None) -> str:
    """Return a compact code from name, number and optional college.

    Parameters
    ----------
    name : str
        Department code.
    number : str
        Course number.
    college : str | None, optional
        College code to include in the resulting string.

    Returns
    -------
    str
        A normalized course identifier.
    """
    cc = "" if college is None else f"-{college}"
    return f"{name}{number}{cc}".upper()
