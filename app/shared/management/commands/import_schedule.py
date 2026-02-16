"""Import timetable data from the cleaned schedule spreadsheet.

The command reads the Excel file, resolves or creates the related academic
structures (college/department/course/curriculum), and then builds the
semester, sections, schedules and sessions. It is meant for one-off loads of
the schedule file shared in Seed_data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, time
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import QuerySet
from tqdm import tqdm

from app.academics.choices import COLLEGE_CODE
from app.academics.ensures import (
    ensure_college,
    ensure_course,
    ensure_curriculum,
    ensure_curriculum_course,
    ensure_department,
)
from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum_course import CurriCourse
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.people.ensure_people import ensure_faculty
from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.people.utils import name_parts_from_row
from app.registry.models import CreditHour
from app.shared.utils import get_in_row, parse_str, to_int
from app.spaces.models.core import Room, Space
from app.timetable.ensures import ensure_semester
from app.timetable.models.schedule import Schedule
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.timetable.models.session import SecSession
from app.timetable.utils import (
    normalize_academic_year,
    parse_time_value,
    parse_weekday,
    split_location,
)

CID_PATTERN = re.compile(
    r"^(?P<dept>[A-Za-z]+)_(?P<num>\d+)_s(?P<section>\d+)$", re.IGNORECASE
)


@dataclass
class ImportStats:
    """Track created objects while importing."""

    colleges: int = 0
    departments: int = 0
    courses: int = 0
    curricula: int = 0
    curriculum_courses: int = 0
    semesters: int = 0
    schedules: int = 0
    spaces: int = 0
    rooms: int = 0
    sections: int = 0
    sessions: int = 0
    faculties: int = 0
    skipped: int = 0
    notes: list[str] = field(default_factory=list)


class Command(BaseCommand):
    """Create schedules/sections/sessions from Seed_data/25-26Sem2_cleaned.xlsx."""

    help = (
        "Import the cleaned 25-26 semester 2 schedule file and populate "
        "colleges/departments/courses/curricula, sections, schedules and sessions."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--source",
            default="Seed_data/25-26Sem2_cleaned.xlsx",
            help="Path to the cleaned schedule workbook.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report without committing changes.",
        )
        parser.add_argument(
            "--start-row",
            type=int,
            default=1,
            help="1-based row offset (including header) to start processing.",
        )

    # ------------------------------------------------------------------ CLI
    def handle(self, *args, **options) -> None:
        source = Path(options["source"])
        dry_run: bool = options["dry_run"]
        start_row: int = options["start_row"]

        if not source.exists():
            raise CommandError(f"Missing schedule file: {source}")

        df = pd.read_excel(source)
        if df.empty:
            raise CommandError(f"No rows found in {source}")

        stats = ImportStats()

        with transaction.atomic():
            for idx, raw_row in tqdm(
                df.iterrows(),
                total=len(df),
                desc="Importing schedule",
            ):
                # excel header line counts as row 1 for reporting
                display_row = idx + 2  # header = 1, dataframe index starts at 0
                if display_row < start_row:
                    continue

                row: dict[str, str] = {
                    str(k): ("" if pd.isna(v) else str(v))
                    for k, v in raw_row.to_dict().items()
                }
                try:
                    self._import_row(row, stats)
                except ValueError as exc:
                    stats.skipped += 1
                    stats.notes.append(f"row {display_row}: {exc}")
                    self.stdout.write(
                        self.style.WARNING(f"Skipping row {display_row}: {exc}")
                    )
                except Exception as exc:
                    raise CommandError(f"Row {display_row} failed: {exc}") from exc

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(
                    self.style.WARNING("Dry-run requested; rolling back changes.")
                )

        self._print_summary(stats)

    # ------------------------------------------------------------------ helpers
    def _import_row(self, row: dict[str, str], stats: ImportStats) -> None:
        """Parse a single row and build related records."""
        dept_code, course_no, section_no = self._parse_cid(get_in_row("cid", row))

        semester = self._resolve_sem(
            ay_str=get_in_row("ay", row),
            semester_str=get_in_row("semester_no", row),
            stats=stats,
        )

        college = self._resolve_college(get_in_row("college", row).lower(), stats)
        department = self._resolve_dpt(dept_code, college, stats)
        course = self._resolve_crs(
            course_no, department, get_in_row("course_title", row), stats
        )
        credit_hours = self._resolve_credit_hours(get_in_row("credit", row))
        curriculum = self._resolve_curri(
            course, college, semester, get_in_row("course_title", row), stats
        )
        curriculum_course = self._resolve_curri_crs(
            curriculum, course, credit_hours, stats
        )

        faculty = self._resolve_faculty(
            get_in_row("instructor", row), department, college, stats
        )

        section = self._resolve_sec(
            semester=semester,
            curriculum_course=curriculum_course,
            section_no=section_no,
            faculty=faculty,
            stats=stats,
        )

        schedule = self._resolve_schedule(
            weekday_raw=get_in_row("weekday", row),
            start_raw=get_in_row("start_time", row),
            end_raw=get_in_row("end_time", row),
            stats=stats,
        )

        room = self._resolve_room(get_in_row("location", row), stats)

        self._resolve_session(section, schedule, room, stats)

    def _parse_cid(self, token: str) -> tuple[str, str, int]:
        """Split the cid (e.g. ACCT_102_s1) into dept, course number and section."""
        _match = CID_PATTERN.match(token)
        if not _match:
            raise ValueError(f"cid '{token}' does not match <dept>_<number>_s<section>")

        dept_code = _match.group("dept").upper()
        course_no = _match.group("num")
        section_str = _match.group("section")
        section_no = to_int(section_str)
        if section_no is None or section_no < 1:
            raise ValueError(f"Invalid section number in cid '{token}'")

        return dept_code, course_no, section_no

    def _resolve_sem(
        self, ay_str: str, semester_str: str, stats: ImportStats
    ) -> Semester:
        ay_code = normalize_academic_year(ay_str)
        if not ay_code:
            raise ValueError("Missing academic year")

        sem_no = to_int(semester_str)
        if sem_no is None:
            raise ValueError("Missing semester number")

        created = not Semester.objects.filter(
            academic_year__code=ay_code, number=sem_no
        ).exists()
        semester = ensure_semester(ay_code, sem_no)
        if created:
            stats.semesters += 1
        return semester

    def _resolve_college(self, token: str, stats: ImportStats) -> College:
        code = COLLEGE_CODE.get(token, token.upper())
        created = not College.objects.filter(code=code).exists()
        college = ensure_college(code)
        if created:
            stats.colleges += 1
        return college

    def _resolve_dpt(
        self, dept_code: str, college: College, stats: ImportStats
    ) -> Department:
        created = not Department.objects.filter(code=dept_code, college=college).exists()
        department = ensure_department(dept_code, college)
        if created:
            stats.departments += 1
        return department

    def _resolve_crs(
        self,
        course_no: str,
        department: Department,
        title: str,
        stats: ImportStats,
    ) -> Course:
        candidates = (
            Course.objects.filter(number=course_no, department=department)
            .order_by("-id")
            .all()
        )
        if candidates:
            return candidates[0]

        created = True
        course = ensure_course(department, course_no, title=title)
        if created:
            stats.courses += 1
        return course

    def _resolve_curri(
        self,
        course: Course,
        college: College,
        semester: Semester,
        title: str,
        stats: ImportStats,
    ) -> Curriculum:
        # sem_start: Optional[date] = (
        #     semester.start_date or semester.academic_year.start_date
        # )
        curricula: QuerySet[Curriculum] = (
            Curriculum.objects.filter(college=college, programs__course=course)
            .distinct()
            .order_by("-is_active", "-creation_date")
        )
        # if sem_start:
        #     curricula = curricula.filter(creation_date__lte=sem_start)

        curriculum: Curriculum | None = curricula.first()
        if curriculum is not None:
            return curriculum

        curriculum = ensure_curriculum("", college, fuzzy_threshold=1.0)
        stats.curricula += 1
        return curriculum

    def _resolve_credit_hours(self, raw: object) -> CreditHour:
        try:
            hours = int(float(str(raw)))
        except (TypeError, ValueError):
            hours = 3
        credit_hour, _ = CreditHour.objects.get_or_create(
            code=hours, defaults={"label": str(hours)}
        )
        return credit_hour

    def _resolve_curri_crs(
        self,
        curriculum: Curriculum,
        course: Course,
        credit_hours: CreditHour,
        stats: ImportStats,
    ) -> CurriCourse:
        created = not CurriCourse.objects.filter(
            curriculum=curriculum, course=course
        ).exists()
        curriculum_course = ensure_curriculum_course(
            curriculum=curriculum,
            course=course,
            credit_code=credit_hours.code,
        )
        if created:
            stats.curriculum_courses += 1
        elif curriculum_course.credit_hours_id != credit_hours.code:
            curriculum_course.credit_hours = credit_hours
            curriculum_course.save(update_fields=["credit_hours"])
        return curriculum_course

    def _resolve_faculty(
        self,
        raw_name: str,
        department: Department,
        college: College,
        stats: ImportStats,
    ) -> Optional[Faculty]:

        _name = parse_str(raw_name)
        if not _name:
            return None

        name_parts = name_parts_from_row(None, raw_name=_name)
        username = Staff.mk_username(
            name_parts.first, name_parts.last, name_parts.middle, unique=True
        )
        created = not Faculty.objects.filter(staff_profile__username=username).exists()
        faculty = ensure_faculty(username, name=name_parts)
        if not faculty.college_id and college:
            faculty.college = college
            faculty.save(update_fields=["college"])
        if created:
            stats.faculties += 1
        return faculty

    def _resolve_sec(
        self,
        semester: Semester,
        curriculum_course: CurriCourse,
        section_no: int,
        faculty: Optional[Faculty],
        stats: ImportStats,
    ) -> Section:
        section, created = Section.objects.get_or_create(
            semester=semester,
            curriculum_course=curriculum_course,
            number=section_no,
            defaults={"faculty": faculty},
        )
        if created:
            stats.sections += 1
        elif faculty and section.faculty_id is None:
            section.faculty = faculty
            section.save(update_fields=["faculty"])
        return section

    def _resolve_schedule(
        self,
        weekday_raw: str,
        start_raw: object,
        end_raw: object,
        stats: ImportStats,
    ) -> Schedule:
        weekday = parse_weekday(weekday_raw)
        start_time = parse_time_value(start_raw)
        end_time = parse_time_value(end_raw)

        schedule, created = Schedule.objects.get_or_create(
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
        )
        if created:
            stats.schedules += 1
        return schedule

    def _resolve_room(self, location_str: str, stats: ImportStats) -> Room:
        space_code, room_code = split_location(location_str)

        if space_code == "TBA":
            space = Space.get_default()
        else:
            space, space_created = Space.objects.get_or_create(
                code=space_code, defaults={"full_name": space_code}
            )
            if space_created:
                stats.spaces += 1

        room, room_created = Room.objects.get_or_create(
            space=space,
            code=room_code or "TBA",
        )
        if room_created:
            stats.rooms += 1
        return room

    def _resolve_session(
        self,
        section: Section,
        schedule: Schedule,
        room: Room,
        stats: ImportStats,
    ) -> SecSession:
        session, created = SecSession.objects.get_or_create(
            section=section,
            schedule=schedule,
            defaults={"room": room},
        )
        if created:
            stats.sessions += 1
        elif session.room_id != room.id:
            session.room = room
            session.save(update_fields=["room"])
        return session

    def _print_summary(self, stats: ImportStats) -> None:
        summary_parts = [
            f"colleges {stats.colleges}",
            f"departments {stats.departments}",
            f"courses {stats.courses}",
            f"curricula {stats.curricula}",
            f"programmed courses {stats.curriculum_courses}",
            f"semesters {stats.semesters}",
            f"schedules {stats.schedules}",
            f"spaces {stats.spaces}",
            f"rooms {stats.rooms}",
            f"sections {stats.sections}",
            f"sessions {stats.sessions}",
            f"faculties {stats.faculties}",
        ]
        if stats.skipped:
            summary_parts.append(f"skipped {stats.skipped}")
        self.stdout.write(
            self.style.SUCCESS("Import completed: " + ", ".join(summary_parts))
        )
        if stats.notes:
            for note in stats.notes:
                self.stdout.write(self.style.NOTICE(f"- {note}"))
