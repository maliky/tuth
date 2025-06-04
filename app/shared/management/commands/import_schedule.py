"""Import course schedule from a CSV file.

The command expects a CSV shaped like ``cleaned_tscc.csv`` and will create
academic years, semesters, courses, instructors, schedules and sections.  It is
intended for use on an empty database when bootstrapping the system.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import IO, Any

from app.shared.management.populate_helpers.sections import parse_int
from django.core.management.base import BaseCommand, CommandParser
from django.utils.dateparse import parse_date, parse_time

from app.academics.admin.widgets import CourseWidget, CurriculumWidget
from app.academics.models import Course
from app.people.models.profile import _ensure_faculty
from app.shared.enums import WEEKDAYS_NUMBER
from app.spaces.admin.widgets import RoomWidget
from app.spaces.models import Room
from app.timetable.admin.widgets import SemesterWidget
from app.timetable.models import Schedule, Section, Semester



class Command(BaseCommand):
    """Load sections and schedules from ``cleaned_tscc.csv`` or provided file."""

    help = "Import timetable schedule data from a CSV file"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "csv_path",
            nargs="?",
            default="/home/mlk/TU/Tuth-project/Docs/Data/cleaned_tscc.csv",
            help="Path to CSV file with schedule data",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(options["csv_path"])
        if not path.exists():
            raise FileNotFoundError(str(path))

        with path.open() as fh:
            populate_sections_from_csv(self, fh)

        self.stdout.write(self.style.SUCCESS("Schedule import completed."))


def populate_sections_from_csv(cmd, fh: IO[str]) -> None:
    """Create timetable objects from a CSV file-like object."""

    reader = csv.DictReader(fh)
    cw = CourseWidget(model=Course, field="code")
    semw = SemesterWidget(model=Semester, field="id")
    rw = RoomWidget(model=Room, field="name")
    curw = CurriculumWidget(model=None, field="short_name")

    for row in reader:
        # ---------------------- semester & Academic year-------------------
        semester_token = row.get("semester")
        semester = semw.clean(semester_token, row)

        # --------------------room & Week day -----------------------------

        room_token = row.get("location", "").strip()
        room = rw.clean(room_token)

        weekday_raw = (row.get("weekday") or "").strip()
        weekday = None
        if weekday_raw:
            try:
                weekday = WEEKDAYS_NUMBER[weekday_raw.upper()]
            except KeyError:
                pass

        instructor_name = row.get("instructor", '').strip()
        faculty = (
            _ensure_faculty(instructor_name, course.college) if instructor_name else None
        )


        raw_start_time = f"{row.get('time_start') or row.get('stime')}"
        raw_end_time = f"{row.get('time_end') or row.get('etime')}"
        start_time = parse_time(raw_start_time)
        end_time = parse_time(raw_end_time)

        # ---------------------- Schedule ------------------------------------
        schedule = Schedule.objects.create(
            weekday=weekday or 1,
            room=room,
            faculty=faculty,
            start_time=start_time,
            end_time=end_time,
        )

        # ---------------------- course ------------------------------------
        course_code = row.get("course_code").strip()
        course_no = row.get("course_no").strip()
        college = row.get("college").strip()
        
        course_token = f"{course_code}{course_num}-{college}"
        
        course = cw.clean(course_token, row, credit_field="credit")

        # Attach course to curriculum when provided
        curr_token = (row.get("curriculum") or "").strip()
        if curr_token:
            curriculum = curw.clean(curr_token, row)
            if curriculum and course:
                curriculum.courses.add(course)

        section_no = parse_int(row.get("section") or row.get("number"))


        schedule = Schedule.objects.create(
            weekday=weekday or 1,
            room=room,
            faculty=faculty,
            start_time=start_time,
            end_time=end_time,
        )

        sts = f"{row.get('sts')}"
        ets = f"{row.get('ets')}"        
        start_date = parse_date(row.get("sts"))
        end_date = parse_date(row.get("ets"))

        Section.objects.create(
            course=course,
            semester=semester,
            number=section_no,
            start_date=start_date,
            end_date=end_date,
            schedule=schedule,
            max_seats=parse_int(row.get("max_seats")) or 30,
        )
