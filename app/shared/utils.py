"""General utility helpers shared between apps."""

from typing import Mapping, Optional, Tuple

from django.core.management.base import BaseCommand
from tablib import Dataset

from app.academics.constants import COURSE_PATTERN
from app.academics.models.college import College
from app.academics.models.department import Department
from app.shared.constants import DATA_COLUMN_REMAP, STYLE_DEFAULT


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
    """Return a course code.  dept.shortname+course.num.

    if short == True use dept.code (without college info)
    """
    _dept_code = dept.code if short else dept.shortname
    return f"{_dept_code}-{number}".upper()


def get_in_row(key: str, row: Optional[Mapping[str, str | None]]) -> str:
    """Return a value from the row (any mapping) safely stripped to a string.

    Does so safely always returning something even if None is in the row.
    """
    try:
        return ((row or {}).get(key) or "").strip()
    except AttributeError as exc:
        raise AttributeError(f"Could not access key '{key}' in row {row}") from exc


def as_title(value: str) -> str:
    """Utility to clean a strip _ from a str and capitalize its words."""
    return value.replace("_", " ").title()


def clean_column_headers(dataset) -> Dataset:
    """Strip blank headers that may appear due to trailing commas."""
    sanitised = [(header or "").strip() for header in dataset.headers]
    dataset.headers = sanitised
    return dataset


def normalize_academic_year(raw: str | None) -> str:
    """Convert various academic year labels to the canonical YY-YY format."""
    text = (raw or "").strip()
    if not text:
        return ""

    token = text.replace(" ", "").replace("/", "-")
    if len(token) == 9 and token[4] == "-":  # 2019-2020
        return f"{token[2:4]}-{token[7:9]}"
    if len(token) == 4 and token.isdigit():  # 2019
        yy = token[2:4]
        return f"{yy}-{int(yy) + 1:02d}"
    if len(token) == 5 and token[2] == "-":  # 19-20
        return token
    return token


def parse_int(value: str | None) -> int | None:
    """Safely convert arbitrary strings to integers."""
    if value is None:
        return None

    token = str(value).strip()
    if not token:
        return None

    try:
        return int(float(token))
    except ValueError:
        return None


def log(cmd: BaseCommand, msg: str, style: str = STYLE_DEFAULT) -> None:
    """Write a styled message to the management command output."""
    style_obj = getattr(cmd.style, style, cmd.style.NOTICE)
    cmd.stdout.write(style_obj(msg))
