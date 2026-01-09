"""Utility helpers for the timetable app."""

from datetime import date
import re
from typing import Optional, Tuple, TypeAlias

from django.core.exceptions import ValidationError
from django.db.models import QuerySet

from app.shared.types import SemesterCodeT


def validate_subperiod(
    *,
    sub_start: Optional[date],
    sub_end: Optional[date],
    container_start: date,
    container_end: date,
    overlap_qs: Optional[QuerySet] = None,
    overlap_message: str = "Overlapping periods.",
    label: str = "period",
) -> None:
    """Validate that a child period fits within its container.

    Parameters
    ----------
    sub_start, sub_end : date | None
        Start and end dates of the sub period.
    container_start, container_end : date
        Bounds of the parent period.
    overlap_qs : QuerySet | None, optional
        Sibling queryset to check for overlaps.
    overlap_message : str, optional
        Error message for overlapping periods.
    label : str, optional
        Field name used in the error dict.

    Raises
    ------
    ValidationError
        If the period is invalid or overlaps with an existing one.
    """
    # chronological order -----------------------------------------------------
    if sub_start and sub_end and sub_end < sub_start:
        raise ValidationError({label: "End date must be after start date."})

    # inside container --------------------------------------------------------
    for dt in (sub_start, sub_end):
        if dt and not (container_start <= dt <= container_end):
            raise ValidationError(
                {
                    label: f"Dates must fall within the parent period "
                    f"({container_start} – {container_end})."
                }
            )

    # overlap check -----------------------------------------------------------
    if overlap_qs is not None and sub_start and sub_end:
        clash = overlap_qs.filter(
            start_date__lt=sub_end,
            end_date__gt=sub_start,
        ).exists()
        if clash:
            raise ValidationError({label: overlap_message})


def get_academic_year(d: date | None = None) -> str:
    """Return the academic year for the date."""
    d = d or date.today()
    start = d.year if d.month >= 9 else d.year - 1
    end = start + 1
    return f"{start % 100:02d}-{end % 100:02d}"


def normalize_academic_year(raw: str | None) -> str:
    """Convert various ay (2019-2020, 2019, 19_20) labels to the canonical YY-YY format."""
    text = (raw or "").strip()
    if not text:
        return ""

    token = text.replace(" ", "").replace("/", "-").replace("_", "-")
    if len(token) == 9 and token[4] == "-":  # 2019-2020
        return f"{token[2:4]}-{token[7:9]}"
    if len(token) == 4 and token.isdigit():  # 2019
        yy = token[2:4]
        return f"{yy}-{int(yy) + 1:02d}"
    if len(token) == 5 and token[2] == "-":  # 19-20
        return token
    return token


def get_semester_code(sem_value: str, year_value: str) -> str:
    """Format a semester code for unambigous semester parsing."""
    _year = normalize_academic_year(year_value)
    return f"{_year}_Sem{sem_value}"


SEMESTER_CODE_RE = re.compile(
    r"^(?P<year>\d{2,4}-\d{2,4})[_-]?(?:Sem|sem|s)(?P<num>[0-4])$"
)


def parse_semester_code(code: str | None) -> SemesterCodeT:
    """Parse strings like '24-25_Sem2' or '24-25s2' into (academic_year_code, semester_no).

    Returns ("", 0) when the pattern does not match. The ay must be separated by '-'.
    """
    if not code:
        return ("", 0)

    text = code.strip().replace(" ", "").replace("/", "-")
    _match = SEMESTER_CODE_RE.match(text)

    if not _match:
        return ("", 0)

    ay_code = _match.group("year")
    sem_no = int(_match.group("num"))

    return ay_code, sem_no


def normalize_semester_code(
    raw: str | None,
    *,
    year_value: str | None = None,
    sem_value: str | None = None,
) -> str:
    """Return a canonical YY-YY_SemN string from mixed semester inputs."""
    ay_code, sem_no = parse_semester_code(raw)
    if ay_code and sem_no:
        return f"{normalize_academic_year(ay_code)}_Sem{sem_no}"

    raw_value = (raw or "").strip()
    if raw_value and year_value:
        return get_semester_code(sem_value=raw_value, year_value=year_value)
    if sem_value and year_value:
        return get_semester_code(sem_value=sem_value, year_value=year_value)

    return ""
