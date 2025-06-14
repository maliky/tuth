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
