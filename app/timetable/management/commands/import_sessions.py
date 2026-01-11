"""Fast session importer for timetable session data."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from app.academics.ensures import (
    ensure_college_id,
    ensure_course_id,
    ensure_curriculum_course_id,
    ensure_curriculum_id,
    ensure_department_id,
)
from app.people.ensure_people import ensure_faculty
from app.people.models.staffs import Staff
from app.people.utils import name_parts_from_row

from app.shared.importing import CsvRowLogger
from app.shared.types import RowStrOptT, SectionCacheT, SessionKeyT

from app.shared.utils import get_in_row, to_int
from app.timetable.choices import WEEKDAYS_NUMBER
from app.timetable.ensures import (
    ensure_room_id,
    ensure_session_id,
    ensure_schedule_id,
    ensure_semester_id,
)
from app.timetable.models.section import Section
from app.timetable.models.session import SecSession


@dataclass
class ImportStats:
    """Track import totals and warnings."""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)


class Command(BaseCommand):
    """Bulk import SecSession entries using preloaded caches.

    Args:
        --file: Path to a TSV file with session rows.
        --semester-code: Fallback semester code when row values are missing.
        --batch-size: Number of rows per bulk insert chunk.

    Examples:
        --semester-code "25-26s2"
    """

    help = "Fast session import (TSV expected)."
    invalid_logger: CsvRowLogger

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-f",
            "--file",
            default="Seed_data/Fundamentals/timetable_sessions_25-26s2.tsv",
            help="Path to TSV file containing sessions.",
        )
        parser.add_argument(
            "--semester-code",
            default="25-26s2",
            help="Fallback semester code when academic_year/semester_no are missing.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=10,
            help="Number of rows per bulk insert chunk.",
        )

    def handle(self, *args, **options) -> None:
        """Import session rows into SecSession.

        Args:
            *args: Unused positional arguments.
            **options: Command options (file, semester_code, batch_size).

        Raises:
            CommandError: When the file is missing or import fails.
        """
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"Missing file: {path}")

        semester_code: str = options["semester_code"]
        batch_size: int = options["batch_size"]

        stats = ImportStats()
        # Log invalid rows to a CSV for follow-up.
        self.invalid_logger = CsvRowLogger(
            "logs/import_sessions_invalid.csv",
            (
                "row_number",
                "reason",
                "academic_year",
                "semester_no",
                "section_no",
                "dept_code",
                "course_dept",
                "course_no",
                "college_code",
                "curriculum",
                "faculty",
                "weekday",
                "start_time",
                "end_time",
                "space",
                "room",
                "location",
                "course_title",
                "credit",
                "credit_hours",
            ),
            "Session import skipped {count} invalid rows; details logged to {path}",
        )

        section_cache = _prime_section_cache()
        pending_sessions: set[SessionKeyT] = set()

        rows_to_create: list[SecSession] = []
        rows_to_update: list[SecSession] = []

        # Increase CSV field size limit to avoid errors
        try:
            csv.field_size_limit(10_000_000)
        except Exception:
            pass

        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row_number, row in enumerate(reader, start=2):
                try:
                    resolved = _resolve_row(
                        row,
                        semester_code=semester_code,
                        section_cache=section_cache,
                        pending_sessions=pending_sessions,
                        rows_to_update=rows_to_update,
                    )
                except ValueError as exc:
                    stats.skipped += 1
                    reason = str(exc)
                    stats.warnings.append(reason)
                    self._log_invalid_row(row_number, row, reason)
                    continue

                if resolved is None:
                    continue
                rows_to_create.append(resolved)
                stats.created += 1

                if len(rows_to_create) >= batch_size:
                    _flush_create(rows_to_create, batch_size)

        if rows_to_create:
            _flush_create(rows_to_create, batch_size)

        if rows_to_update:
            SecSession.objects.bulk_update(rows_to_update, ["room"], batch_size=500)
            stats.updated += len(rows_to_update)

        self._print_summary(stats)
        self.invalid_logger.report(self)


    def _print_summary(self, stats: ImportStats) -> None:
        """Print the import summary to stdout."""
        summary = f"sessions {stats.created}"
        if stats.updated:
            summary += f", rooms updated {stats.updated}"
        if stats.skipped:
            summary += f", skipped {stats.skipped}"
        self.stdout.write(self.style.SUCCESS(f"Session import complete: {summary}"))
        for note in stats.warnings[:10]:
            self.stdout.write(self.style.WARNING(f"- {note}"))


def _resolve_row(
    row: RowStrOptT,
    *,
    semester_code: str,
    section_cache: SectionCacheT,
    pending_sessions: set[SessionKeyT],
    rows_to_update: list[SecSession],
) -> SecSession | None:
    """Resolve a row into a SecSession or queue updates.

    Args:
        row: Session row with keys like weekday, start_time, end_time, section_no.
        semester_code: Fallback semester code when row values are missing.
        section_cache: Cache of section keys to (id, faculty_id).
        pending_sessions: Tracks session keys already queued for creation.
        rows_to_update: List of sessions to update when room differs.

    Returns:
        A new SecSession to create, or None when the row updates an existing
        session.

    Raises:
        ValueError: When the row contains invalid section_no values.

    Examples:
        semester_code: "25-26s2"
    """

    semester_id = _resolve_semester_id(row, semester_code)
    curriculum_course_id = _resolve_curriculum_course_id(row)
    schedule_id = _resolve_schedule_id(row)
    room_id = _resolve_room_id(row)
    faculty_id = _resolve_faculty_id(row)

    section_no = to_int(get_in_row("section_no", row))
    if section_no <= 0:
        # this is to prevent a DB failure, number >0
        raise ValueError(f"Invalid section_no value: {get_in_row('section_no', row)}")

    section_id = _resolve_section_id(
        semester_id, curriculum_course_id, section_no, faculty_id, section_cache
    )

    session_key: SessionKeyT = (section_id, schedule_id)

    existing = ensure_session_id(
        section_id,
        schedule_id,
        room_id=room_id,
        create=False,
    )
    if existing:
        session_id, existing_room_id = existing
        if existing_room_id != room_id:
            rows_to_update.append(SecSession(id=session_id, room_id=room_id))
        return None

    if session_key in pending_sessions:
        return None
    pending_sessions.add(session_key)
    return SecSession(section_id=section_id, schedule_id=schedule_id, room_id=room_id)


def _resolve_schedule_id(row: RowStrOptT) -> int:
    """Resolve schedule id from weekday/start/end values.

    Args:
        row: Row with weekday, start_time, end_time.

    Returns:
        Schedule id.

    Raises:
        ValueError: When weekday or time parsing fails.

    Examples:
        weekday: "Mon", start_time: "08:30", end_time: "09:45"
    """
    weekday = _parse_weekday(get_in_row("weekday", row))
    start_time = _parse_time(get_in_row("start_time", row), "start_time")
    end_time = _parse_time(get_in_row("end_time", row), "end_time")
    return ensure_schedule_id(weekday, start_time, end_time)


def _resolve_room_id(row: RowStrOptT) -> int:
    """Resolve room id from space/room or a combined location string.

    Args:
        row: Row with space/room or location value.

    Returns:
        Room id.

    Examples:
        location: "NB-201"
    """
    space_code = get_in_row("space", row)
    room_code = get_in_row("room", row)
    if not space_code or not room_code:
        space_code, room_code = _split_location(get_in_row("location", row))

    return ensure_room_id(space_code or "TBA", room_code or "TBA")


def _resolve_semester_id(row: RowStrOptT, semester_code: str) -> int:
    """Resolve a semester id from row values or a fallback code.

    Args:
        row: Row with academic_year and semester_no values.
        semester_code: Fallback semester code like "25-26s2".

    Returns:
        Semester id from ensure_semester_id.
    """
    academic_year = get_in_row("academic_year", row)
    semester_no = get_in_row("semester_no", row)
    default = semester_code if semester_code else None
    return ensure_semester_id(academic_year, semester_no, default=default)


def _resolve_curriculum_course_id(row: RowStrOptT) -> int:
    """Resolve curriculum_course id for a session row.

    Args:
        row: Row with dept_code/course_dept, course_no, curriculum, credit.

    Returns:
        CurriculumCourse id.

    Raises:
        ValueError: When required dept_code or course_no values are missing.

    Examples:
        dept_code: "ACCT", course_no: "101"
    """
    college_code = get_in_row("college_code", row)
    dept_code = get_in_row("dept_code", row) or get_in_row("course_dept", row)
    course_no = get_in_row("course_no", row)
    curriculum_name = get_in_row("curriculum", row)
    if not dept_code or not course_no:
        raise ValueError("Missing dept_code/course_no for session row")

    college_id = ensure_college_id(college_code)
    department_id = ensure_department_id(dept_code, college_id)
    course_id = ensure_course_id(
        department_id, course_no, get_in_row("course_title", row) or ""
    )
    curriculum_id = ensure_curriculum_id(curriculum_name, college_id, fuzzy_threshold=1.0)
    credit_raw = get_in_row("credit", row) or get_in_row("credit_hours", row)
    credit_code = to_int(credit_raw, default=3)
    return ensure_curriculum_course_id(curriculum_id, course_id, credit_code)


def _resolve_faculty_id(row: RowStrOptT) -> int | None:
    """Resolve the faculty id for a session row.

    Args:
        row: Row with faculty name or name parts.

    Returns:
        Faculty id or None when no faculty data is provided.

    Examples:
        faculty: "Dylan, John A"
    """
    faculty_name = get_in_row("faculty", row)
    if not faculty_name and not get_in_row("last_name", row):
        return None
    name_parts = name_parts_from_row(row, fullname_key="faculty", raw_name=faculty_name)
    username = Staff.mk_username(
        name_parts.first, name_parts.last, name_parts.middle, unique=True
    )
    faculty = ensure_faculty(username, name=name_parts)
    return faculty.id


def _resolve_section_id(
    semester_id: int,
    curriculum_course_id: int,
    section_no: int,
    faculty_id: int | None,
    cache: SectionCacheT,
) -> int:
    """Resolve or create a section id for a session row.

    Args:
        semester_id: Target semester id.
        curriculum_course_id: Target curriculum_course id.
        section_no: Section number.
        faculty_id: Optional faculty id.
        cache: Cache of section keys to (id, faculty_id).

    Returns:
        Section id.
    """
    key = (semester_id, curriculum_course_id, section_no)
    cached = cache.get(key)
    if cached:
        section_id, existing_faculty_id = cached
        if faculty_id and existing_faculty_id is None:
            Section.objects.filter(id=section_id).update(faculty_id=faculty_id)
            cache[key] = (section_id, faculty_id)
        return section_id

    section, created = Section.objects.get_or_create(
        semester_id=semester_id,
        curriculum_course_id=curriculum_course_id,
        number=section_no,
        defaults={"faculty_id": faculty_id},
    )
    if not created and faculty_id and section.faculty_id is None:
        section.faculty_id = faculty_id
        section.save(update_fields=["faculty_id"])

    cache[key] = (section.id, section.faculty_id)
    return section.id


def _parse_weekday(value: str) -> int:
    """Normalize weekday values to the WEEKDAYS_NUMBER enum.

    Args:
        value: Raw weekday string (label or digit).

    Returns:
        Weekday integer value.

    Raises:
        ValueError: When the weekday is not recognized.

    Examples:
        "Mon" -> 1
    """
    token = (value or "").strip().lower()
    if not token:
        return WEEKDAYS_NUMBER.TBA
    if token.isdigit():
        return int(token)
    mapping = {label.lower(): num for num, label in WEEKDAYS_NUMBER.choices}
    if token not in mapping:
        raise ValueError(f"Unknown weekday '{value}'")
    return mapping[token]


def _parse_time(value: str, label: str) -> time:
    """Parse a time value from common string formats.

    Args:
        value: Raw time string.
        label: Field label for error messages.

    Returns:
        Parsed time value.

    Raises:
        ValueError: When the value is missing or unparsable.

    Examples:
        "08:30", "08:30:00", "8:30 AM"
    """
    text = (value or "").strip()
    if not text:
        raise ValueError(f"Missing {label} value")
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Could not parse {label} value '{value}'")


def _split_location(raw: str) -> tuple[str, str]:
    """Split a location string into space and room codes.

    Args:
        raw: Location string from the input row.

    Returns:
        A tuple of (space_code, room_code).

    Examples:
        "NB-201" -> ("NB", "201")
    """
    text = (raw or "").strip()
    if not text or text.lower() == "tba":
        return "TBA", "TBA"

    normalized = " ".join(text.split())
    normalized = normalized.replace(" -", "-").replace("- ", "-")

    for sep in ("-", "/", " "):
        if sep in normalized:
            left, right = normalized.split(sep, 1)
            return left.strip().upper(), right.strip() or "TBA"

    return normalized.upper(), normalized


def _prime_section_cache() -> SectionCacheT:
    """Prime a cache for Section lookups.

    Returns:
        A cache keyed by (semester_id, curriculum_course_id, number) to
        (section_id, faculty_id).
    """
    cache: SectionCacheT = {}
    for (
        semester_id,
        curriculum_course_id,
        number,
        pk,
        faculty_id,
    ) in Section.objects.values_list(
        "semester_id", "curriculum_course_id", "number", "id", "faculty_id"
    ):
        cache[(semester_id, curriculum_course_id, number)] = (pk, faculty_id)
    return cache


def _flush_create(rows: list[SecSession], batch_size: int) -> None:
    """Bulk create SecSession rows.

    Args:
        rows: List of SecSession entries to create.
        batch_size: Chunk size for the bulk insert.
    """
    with transaction.atomic():
        SecSession.objects.bulk_create(rows, ignore_conflicts=True, batch_size=batch_size)
    rows.clear()

