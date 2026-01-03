"""Utility helpers for the timetable app."""

from datetime import date
from typing import Optional

from django.core.exceptions import ValidationError
from django.db.models import QuerySet


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


def get_semester_code(sem_value: str, year_value: str) -> str:
    """Format a semester code for unambigous semester parsing."""
    _year = normalize_academic_year(year_value)
    return f"{_year}_Sem{sem_value}"


def mk_semester_code(year: str, sem_no: float | int) -> str:
    r"""Given a year in format YYYY/YYYY and a sem no return the semester code.

    The code is \r'^(?P<year>\\d{2}-\\d{2})_Sem(?P<num>\\d+)$'.
    """
    if not year or not sem_no:
        return ""
    ya, yb = year.split("/")
    if isinstance(sem_no, float):
        sem_no = int(sem_no)
    return f"{ya[2:]}-{yb[2:]}-Sem{sem_no}"
