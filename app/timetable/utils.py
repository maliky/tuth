"""Utility helpers for the timetable app."""

from datetime import date, datetime, time
import re
from typing import Optional

from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.utils import timezone

from app.shared.utils import parse_str
from app.shared.types import SemesterCodeT
from app.timetable.choices import WEEKDAYS_NUMBER


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


def get_academic_year(d: Optional[date] = None) -> str:
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


def normalize_academic_year(raw: Optional[str]) -> str:
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
    text = parse_str(raw)
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


def get_sem_code(sem_value: str, year_value: str) -> str:
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


def parse_sem_code(code: Optional[str]) -> SemesterCodeT:
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


def normalize_sem_code(
    sem_code: Optional[str],
    *,
    year_value: Optional[str] = None,
    sem_value: Optional[str] = None,
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
    ay_code, sem_no = parse_sem_code(sem_code)
    if ay_code and sem_no:
        return f"{normalize_academic_year(ay_code)}_Sem{sem_no}"

    raw_value = parse_str(sem_code)
    if raw_value and year_value:
        return get_sem_code(sem_value=raw_value, year_value=year_value)
    if sem_value and year_value:
        return get_sem_code(sem_value=sem_value, year_value=year_value)

    return ""


def parse_weekday(value: object) -> int:
    """Normalize weekday values to the WEEKDAYS_NUMBER enum.

    Args:
        value: Raw weekday string or number.

    Returns:
        Weekday integer value.

    Raises:
        ValueError: When the weekday is not recognized.
    """
    token = parse_str(value, "lower", dft="")
    if not token:
        return WEEKDAYS_NUMBER.TBA
    if token.isdigit():
        return int(token)
    mapping = {label.lower(): num for num, label in WEEKDAYS_NUMBER.choices}
    if token not in mapping:
        raise ValueError(f"Unknown weekday '{value}'")
    return mapping[token]


def parse_time_value(value: object, *, label: str = "time") -> time:
    """Parse a time value from common string formats.

    Args:
        value: Raw time input.
        label: Field label for error messages.

    Returns:
        Parsed time value.

    Raises:
        ValueError: When the value is missing or unparsable.
    """
    if isinstance(value, time):
        return value
    raw_text = "" if not value else str(value)
    text = parse_str(raw_text)
    if not text:
        raise ValueError(f"Missing {label} value")
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Could not parse {label} value '{text}'")


def split_location(raw: object) -> tuple[str, str]:
    """Split a location string into space and room codes.

    Args:
        raw: Location string from the input row.

    Returns:
        A tuple of (space_code, room_code).
    """
    raw_value = "" if not raw else str(raw)
    text = parse_str(raw_value)
    if not text or text.lower() == "tba":
        return "TBA", "TBA"

    normalized = re.sub(r"\s+", " ", text)
    normalized = normalized.replace(" -", "-").replace("- ", "-")

    for sep in ("-", "/", " "):
        if sep in normalized:
            left, right = normalized.split(sep, 1)
            return left.strip().upper(), right.strip() or "TBA"

    _match = re.match(r"(?P<prefix>[A-Za-z]+)(?P<rest>.*)", normalized)
    if _match:
        return _match.group("prefix").upper(), _match.group("rest").strip() or "TBA"

    return normalized.upper(), normalized


def format_datetime(value: Optional[datetime]) -> str:
    """Return a formatted datetime string for UI displays."""
    if not value:
        return "-"
    return timezone.localtime(value).strftime("%b %d, %Y %H:%M")


def format_short_datetime(value: Optional[datetime]) -> str:
    """Return a short datetime string for compact UI badges."""
    if not value:
        return "-"
    return timezone.localtime(value).strftime("%b %d, %H:%M")
