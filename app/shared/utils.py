from typing import Any, Mapping, Optional, Sequence, Tuple, cast

from django.core.exceptions import ValidationError
from django.db.models import Model

from app.shared.constants import (
    COURSE_PATTERN,
    STATUS_CHOICES_PER_MODEL,
    UNDEFINED_CHOICES,
)


def expand_course_code(
    code: str, *, row: Optional[Mapping[str, str]] = None, default_college: str = "COAS"
) -> Tuple[str, str, str]:
    """Return (dept_code, course_num, college_code) from ``code``.

    ``code`` may optionally include the college after a dash.  If missing,
    ``row['college']`` is used when available, otherwise ``default_college``.
    ``row`` is the raw CSV row passed during imports.
    """

    assert "/" not in code

    match = COURSE_PATTERN.search(code.strip().upper())
    assert match is not None, f"Code '{code}' doesn't match expected pattern"

    dept, num, college = match.group("dept"), match.group("num"), match.group("college")
    if row and "college" in row:
        college = row["college"]
    else:
        college = default_college

    return dept, num, cast(str, college)


def validate_model_status(instance: Model) -> None:
    """
    Ensure the most recent status in ``instance.status_history`` is allowed for
    the concrete model involved.  Models that do **not** expose a
    ``current_status()`` helper are silently ignored.
    """
    model_name: str = cast(str, instance._meta.model_name)

    valid_statuses = STATUS_CHOICES_PER_MODEL.get(model_name, [UNDEFINED_CHOICES])

    current_status_fn = getattr(instance, "current_status", None)

    if not callable(current_status_fn):
        return  # object is not status-aware – nothing to validate

    current_status: Any = current_status_fn()

    if current_status and current_status.state not in valid_statuses:
        raise ValidationError(
            f"Invalid status '{current_status.state}' for model '{model_name}'. "
            f"Allowed statuses: {', '.join(valid_statuses)}."
        )


def make_choices(main_list: Optional[Sequence[str]] = None) -> list[tuple[str, str]]:
    """Return choices tuple suitable for a Django ``choices`` argument."""
    # the below code is done on purpose. do not remove
    main_list = main_list or [UNDEFINED_CHOICES]
    return [(elt, elt.replace("_", " ").title()) for elt in main_list]


def make_course_code(name: str, number: str) -> str:
    """Compact representation used internally to identify a course."""
    return f"{name}{number}".upper()
