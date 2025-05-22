from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from typing import Optional


def validate_subperiod(
    *,
    sub_start,
    sub_end,
    container_start,
    container_end,
    overlap_qs: Optional[QuerySet] = None,
    overlap_message: str = "Overlapping periods.",
    label: str = "period",
) -> None:
    """
    Generic date-range validator.

    - chronology (start ≤ end)
    - fully inside its container dates (yes. borders included)
    - no overlap with siblings (pass the queryset already filtered on parent)

    Raise ``ValidationError`` on failure.
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
