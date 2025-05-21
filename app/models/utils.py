from django.core.exceptions import ValidationError
from app.constants import STATUS_CHOICES_PER_MODEL, UNDEFINED_CHOICES
from typing import Optional
from django.db.models import QuerySet


def validate_model_status(instance):
    model_name = instance._meta.model_name  # 'curriculum' or 'document'
    valid_statuses = STATUS_CHOICES_PER_MODEL.get(model_name, [UNDEFINED_CHOICES])
    current_status = instance.current_status()
    if current_status and current_status.state not in valid_statuses:
        raise ValidationError(
            f"Invalid status '{current_status.state}' for model '{model_name}'. "
            f"Allowed statuses: {', '.join(valid_statuses)}."
        )
    return None


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
