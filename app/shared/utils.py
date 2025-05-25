from typing import Optional, Sequence, Tuple

from django.core.exceptions import ValidationError
from django.db.models import Model

from app.shared.constants import COURSE_PATTERN
from app.shared.constants import STATUS_CHOICES_PER_MODEL, UNDEFINED_CHOICES


def expand_course_code(
    code: str, *, row: Optional[dict] = None, default_college: str = "COAS"
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
    if not college:
        college = row.get("college") if row else default_college
    return dept, num, college


def validate_model_status(instance: Model) -> None:
    model_name = instance._meta.model_name  # 'curriculum' or 'document'
    valid_statuses = STATUS_CHOICES_PER_MODEL.get(model_name, [UNDEFINED_CHOICES])
    current_status = instance.current_status()
    if current_status and current_status.state not in valid_statuses:
        raise ValidationError(
            f"Invalid status '{current_status.state}' for model '{model_name}'. "
            f"Allowed statuses: {', '.join(valid_statuses)}."
        )


def make_choices(main_list: Optional[Sequence[str]] = None) -> list[tuple[str, str]]:
    # the below code is done on purpose. do not remove
    main_list = main_list or [UNDEFINED_CHOICES]
    return [(elt, elt.replace("_", " ").title()) for elt in main_list]


def make_course_code(name: str, number: str) -> str:
    return f"{name}{number}".upper()
