"""Fast session importer for timetable session data."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path
from typing import Optional

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
from app.shared.types import (
    RoomCacheT,
    RowStrOptT,
    ScheduleCacheT,
    SectionCacheT,
    SessionCacheT,
)
from app.shared.utils import get_in_row, to_int
from app.spaces.models.core import Room, Space
from app.timetable.choices import WEEKDAYS_NUMBER
from app.timetable.ensures import ensure_semester_id
from app.timetable.models.schedule import Schedule
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

        schedule_cache = self._prime_schedule_cache()
        room_cache = self._prime_room_cache()
        section_cache = self._prime_section_cache()
        session_cache = self._prime_session_cache()

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
                    resolved = self._resolve_row(
                        row,
                        semester_code=semester_code,
                        schedule_cache=schedule_cache,
                        room_cache=room_cache,
                        section_cache=section_cache,
                        session_cache=session_cache,
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
                    self._flush_create(rows_to_create, batch_size)

        if rows_to_create:
            self._flush_create(rows_to_create, batch_size)

        if rows_to_update:
            SecSession.objects.bulk_update(rows_to_update, ["room"], batch_size=500)
            stats.updated += len(rows_to_update)

        self._print_summary(stats)
        self.invalid_logger.report(self)

    def _resolve_row(
        self,
        row: RowStrOptT,
        *,
        semester_code: str,
        schedule_cache: ScheduleCacheT,
        room_cache: RoomCacheT,
        section_cache: SectionCacheT,
        session_cache: SessionCacheT,
        rows_to_update: list[SecSession],
    ) -> SecSession | None:
        """Resolve a row into a SecSession or queue updates.

        Args:
            row: Session row with keys like weekday, start_time, end_time, section_no.
            semester_code: Fallback semester code when row values are missing.
            schedule_cache: Cache of schedule keys to ids.
            room_cache: Cache of room keys to ids.
            section_cache: Cache of section keys to (id, faculty_id).
            session_cache: Cache of (section_id, schedule_id) to (id, room_id).
            rows_to_update: List of sessions to update when room differs.

        Returns:
            A new SecSession to create, or None when the row updates an existing
            session.

        Raises:
            ValueError: When the row contains invalid section_no values.

        Examples:
            semester_code: "25-26s2"
        """

        semester_id = self._resolve_semester_id(row, semester_code)
        curriculum_course_id = self._resolve_curriculum_course_id(row)
        schedule_id = self._resolve_schedule_id(row, schedule_cache)
        room_id = self._resolve_room_id(row, room_cache)
        faculty_id = self._resolve_faculty_id(row)

        section_no = to_int(get_in_row("section_no", row))
        if section_no <= 0:
            # this is to prevent a DB failure, number >0
            raise ValueError(f"Invalid section_no value: {get_in_row('section_no', row)}")

        section_id = self._resolve_section_id(
            semester_id, curriculum_course_id, section_no, faculty_id, section_cache
        )

        session_key = (section_id, schedule_id)

        existing = session_cache.get(session_key)
        if existing:
            session_id, existing_room_id = existing
            if existing_room_id != room_id:
                rows_to_update.append(SecSession(id=session_id, room_id=room_id))
                session_cache[session_key] = (session_id, room_id)
            return None

        session_cache[session_key] = (0, room_id)
        return SecSession(section_id=section_id, schedule_id=schedule_id, room_id=room_id)

    def _log_invalid_row(self, row_number: int, row: RowStrOptT, reason: str) -> None:
        """Capture invalid session rows for later inspection."""
        self.invalid_logger.log(
            {
                "row_number": str(row_number),
                "reason": reason,
                "academic_year": (row.get("academic_year") or ""),
                "semester_no": (row.get("semester_no") or ""),
                "section_no": (row.get("section_no") or ""),
                "dept_code": (row.get("dept_code") or ""),
                "course_dept": (row.get("course_dept") or ""),
                "course_no": (row.get("course_no") or ""),
                "college_code": (row.get("college_code") or ""),
                "curriculum": (row.get("curriculum") or ""),
                "faculty": (row.get("faculty") or ""),
                "weekday": (row.get("weekday") or ""),
                "start_time": (row.get("start_time") or ""),
                "end_time": (row.get("end_time") or ""),
                "space": (row.get("space") or ""),
                "room": (row.get("room") or ""),
                "location": (row.get("location") or ""),
                "course_title": (row.get("course_title") or ""),
                "credit": (row.get("credit") or ""),
                "credit_hours": (row.get("credit_hours") or ""),
            }
        )

    def _resolve_semester_id(self, row: RowStrOptT, semester_code: str) -> int:
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

    def _resolve_curriculum_course_id(self, row: RowStrOptT) -> int:
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
        curriculum_id = ensure_curriculum_id(
            curriculum_name, college_id, fuzzy_threshold=1.0
        )
        credit_raw = get_in_row("credit", row) or get_in_row("credit_hours", row)
        credit_code = to_int(credit_raw, default=3)
        return ensure_curriculum_course_id(curriculum_id, course_id, credit_code)

    def _resolve_faculty_id(self, row: RowStrOptT) -> int | None:
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
        name_parts = name_parts_from_row(
            row, fullname_key="faculty", raw_name=faculty_name
        )
        username = Staff.mk_username(
            name_parts.first, name_parts.last, name_parts.middle, unique=True
        )
        faculty = ensure_faculty(username, name=name_parts)
        return faculty.id

    def _resolve_section_id(
        self,
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

    def _resolve_schedule_id(
        self,
        row: RowStrOptT,
        cache: ScheduleCacheT,
    ) -> int:
        """Resolve schedule id from weekday/start/end values.

        Args:
            row: Row with weekday, start_time, end_time.
            cache: Cache of (weekday, start_time, end_time) to id.

        Returns:
            Schedule id.

        Raises:
            ValueError: When weekday or time parsing fails.

        Examples:
            weekday: "Mon", start_time: "08:30", end_time: "09:45"
        """
        weekday = self._parse_weekday(get_in_row("weekday", row))
        start_time = self._parse_time(get_in_row("start_time", row), "start_time")
        end_time = self._parse_time(get_in_row("end_time", row), "end_time")
        key = (weekday, start_time, end_time)
        cached = cache.get(key)
        if cached:
            return cached
        schedule, _ = Schedule.objects.get_or_create(
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
        )
        cache[key] = schedule.id
        return schedule.id

    def _resolve_room_id(
        self,
        row: RowStrOptT,
        cache: RoomCacheT,
    ) -> int:
        """Resolve room id from space/room or a combined location string.

        Args:
            row: Row with space/room or location value.
            cache: Cache of (space_code, room_code) to id.

        Returns:
            Room id.

        Examples:
            location: "NB-201"
        """
        space_code = get_in_row("space", row)
        room_code = get_in_row("room", row)
        if not space_code or not room_code:
            space_code, room_code = self._split_location(get_in_row("location", row))

        key = (space_code or "TBA", room_code or "TBA")
        cached = cache.get(key)
        if cached:
            return cached
        if key[0] == "TBA":
            space = Space.get_default()
        else:
            space, _ = Space.objects.get_or_create(
                code=key[0],
                defaults={"full_name": key[0]},
            )
        room, _ = Room.objects.get_or_create(space=space, code=key[1])
        cache[key] = room.id
        return room.id

    def _parse_weekday(self, value: str) -> int:
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

    def _parse_time(self, value: str, label: str) -> time:
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

    def _split_location(self, raw: str) -> tuple[str, str]:
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

    def _prime_schedule_cache(self) -> ScheduleCacheT:
        """Prime a cache for Schedule lookups.

        Returns:
            A cache keyed by (weekday, start_time, end_time) to schedule id.
        """
        cache: ScheduleCacheT = {}
        for weekday, start, end, pk in Schedule.objects.values_list(
            "weekday", "start_time", "end_time", "id"
        ):
            cache[(weekday, start, end)] = pk
        return cache

    def _prime_room_cache(self) -> RoomCacheT:
        """Prime a cache for Room lookups.

        Returns:
            A cache keyed by (space_code, room_code) to room id.
        """
        cache: RoomCacheT = {}
        for space_code, room_code, pk in Room.objects.values_list(
            "space__code", "code", "id"
        ):
            cache[(space_code, room_code)] = pk
        return cache

    def _prime_section_cache(self) -> SectionCacheT:
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

    def _prime_session_cache(self) -> SessionCacheT:
        """Prime a cache for SecSession lookups.

        Returns:
            A cache keyed by (section_id, schedule_id) to (session_id, room_id).
        """
        cache: SessionCacheT = {}
        for section_id, schedule_id, pk, room_id in SecSession.objects.values_list(
            "section_id", "schedule_id", "id", "room_id"
        ):
            cache[(section_id, schedule_id)] = (pk, room_id)
        return cache

    def _flush_create(self, rows: list[SecSession], batch_size: int) -> None:
        """Bulk create SecSession rows.

        Args:
            rows: List of SecSession entries to create.
            batch_size: Chunk size for the bulk insert.
        """
        with transaction.atomic():
            SecSession.objects.bulk_create(
                rows, ignore_conflicts=True, batch_size=batch_size
            )
        rows.clear()

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
