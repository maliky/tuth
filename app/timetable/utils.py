"""Utility helpers for the timetable app."""

from datetime import date
import re
from typing import Optional, Tuple, TypeAlias, TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db.models import QuerySet

from app.shared.types import SemesterCodeT

if TYPE_CHECKING:
    from app.timetable.models.semester import Semester

OpenRegistrationSemesterResultT: TypeAlias = Tuple["Semester | None", str | None]


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

    Args:
        sub_start: Start date for the sub period.
        sub_end: End date for the sub period.
        container_start: Lower bound of the parent period.
        container_end: Upper bound of the parent period.
        overlap_qs: Collection of sibling periods to check for overlaps.
        overlap_message: Message used when an overlap is found.
        label: Field name used in the ValidationError payload.

    Raises:
        ValidationError: If the period is invalid or overlaps with an existing one.
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
    """Return the academic year label for a date.

    Args:
        d: Date to evaluate; when omitted, uses today's date.

    Returns:
        Academic year label in YY-YY format.

    Examples:
        A date in September 2024 yields "24-25".
    """
    d = d or date.today()
    start = d.year if d.month >= 9 else d.year - 1
    end = start + 1
    return f"{start % 100:02d}-{end % 100:02d}"


def normalize_academic_year(raw: str | None) -> str:
    """Convert various labels to the canonical YY-YY academic year format.

    Args:
        raw: Raw academic year label to normalize.

    Returns:
        Canonical YY-YY string, or an empty string when input is blank.

    Examples:
        "2019-2020" becomes "19-20".
        "2019" becomes "19-20".
        "19_20" becomes "19-20".
    """
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
    """Build a semester code from year and semester values.

    Args:
        sem_value: Semester number or label.
        year_value: Academic year label to normalize.

    Returns:
        A canonical semester code such as "24-25_Sem2".

    Examples:
        sem_value "2" and year_value "2024-2025" yields "24-25_Sem2".
        sem_value "1" and year_value "24-25" yields "24-25_Sem1".
    """
    _year = normalize_academic_year(year_value)
    return f"{_year}_Sem{sem_value}"


SEMESTER_CODE_RE = re.compile(
    r"^(?P<year>\d{2,4}-\d{2,4})[_-]?(?:Sem|sem|s)(?P<num>[0-4])$"
)


def parse_semester_code(code: str | None) -> SemesterCodeT:
    """Parse semester code strings into their year and number components.

    Args:
        code: Semester code string to parse.

    Returns:
        Two values: academic_year_code and semester_no, or ("", 0) when no match.

    Examples:
        "24-25_Sem2" returns ("24-25", 2).
        "24-25s2" returns ("24-25", 2).
        "2024-2025_Sem1" returns ("2024-2025", 1).
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
    sem_code: str | None,
    *,
    year_value: str | None = None,
    sem_value: str | None = None,
) -> str:
    """Return a canonical YY-YY_SemN string from mixed semester inputs.

    Args:
        sem_code: Semester string to parse or normalize.
        year_value: Year label used when sem_code is a semester-only value.
        sem_value: Semester label used with year_value when sem_code is blank.

    Returns:
        A canonical semester code or an empty string when inputs are insufficient.

    Examples:
        "24-25s2" yields "24-25_Sem2".
        sem_code "2" with year_value "24-25" yields "24-25_Sem2".
        sem_value "1" with year_value "2024-2025" yields "24-25_Sem1".
    """
    ay_code, sem_no = parse_semester_code(sem_code)
    if ay_code and sem_no:
        return f"{normalize_academic_year(ay_code)}_Sem{sem_no}"

    raw_value = (sem_code or "").strip()
    if raw_value and year_value:
        return get_semester_code(sem_value=raw_value, year_value=year_value)
    if sem_value and year_value:
        return get_semester_code(sem_value=sem_value, year_value=year_value)

    return ""


def resolve_registration_open_semester() -> OpenRegistrationSemesterResultT:
    """Return the registration-open semester and an optional error message."""
    from app.timetable.models.semester import Semester

    try:
        semester = Semester.get_registration_open_semester()
    except ValidationError as exc:
        return None, str(exc)
    return semester, None
