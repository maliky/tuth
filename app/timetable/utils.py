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


def get_current_semester(today: Optional[date] = None):
    """Return the Semester active for *today* or ``None`` if none."""
    from app.timetable.models.semester import Semester

    today = today or date.today()
    return (
        Semester.objects.filter(start_date__lte=today, end_date__gte=today)
        .order_by("start_date")
        .first()
    )


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
