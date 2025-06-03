"""Helpers to import section data from CSV.

This module provides :func:`populate_sections_from_csv` which creates the
fundamental timetable objects (academic years, semesters, courses, instructors,
schedules and sections) from a CSV stream.  It is designed for seeding an empty
database using the exported ``cleaned_tscc.csv`` file.
"""

from __future__ import annotations

import csv
from typing import IO

from django.utils.dateparse import parse_date, parse_time

from app.academics.admin.widgets import CourseWidget, CurriculumWidget
from app.academics.models import Course
from app.people.models.profile import _ensure_faculty
from app.shared.enums import WEEKDAYS_NUMBER
from app.spaces.admin.widgets import RoomWidget
from app.spaces.models import Room
from app.timetable.admin.widgets import SemesterWidget
from app.timetable.models import Schedule, Section, Semester


def _parse_int(value: str | None) -> int | None:
    """Return ``int(value)`` when possible.

    Handles numbers represented as ``"1.0"`` or ``"1"`` and ignores
    non-numeric strings by returning ``None``.
    """

    if value is None:
        return None

    token = str(value).strip()
    try:
        return int(float(token))
    except ValueError:
        return None


def populate_sections_from_csv(cmd, fh: IO[str]) -> None:
    """Create timetable objects from a CSV file-like object."""

    reader = csv.DictReader(fh)
    cw = CourseWidget(model=Course, field="code")
    semw = SemesterWidget(model=Semester, field="id")
    rw = RoomWidget(model=Room, field="name")
    curw = CurriculumWidget(model=None, field="short_name")

    for row in reader:
        # ---------------------- course ------------------------------------
        course_token = row.get("course")
        if not course_token:
            number_raw = row.get("course_no") or ""
            try:
                course_num = str(int(float(number_raw)))
            except ValueError:
                course_num = number_raw.strip()
            course_token = f"{row.get('course_code', '').strip()}{course_num}"

        course = cw.clean(course_token, row, credit_field="credit")

        # Attach course to curriculum when provided
        curr_token = (row.get("curriculum") or "").strip()
        if curr_token:
            curriculum = curw.clean(curr_token, row)
            if curriculum:
                curriculum.courses.add(course)

        # ---------------------- semester ----------------------------------
        semester_token = row.get("semester")
        if semester_token:
            semester_token = semester_token.replace("-Sem", "_Sem")
        semester = semw.clean(semester_token, row)

        section_no = _parse_int(row.get("section") or row.get("number"))

        # ---------------------- faculty & room -----------------------------

        instructor_name = (row.get("instructor") or "").strip()
        faculty = _ensure_faculty(instructor_name, course.college) if instructor_name else None

        room_token = (row.get("location") or row.get("room") or "").strip()
        room = rw.clean(room_token) if room_token else None

        weekday_raw = (row.get("weekday") or "").strip()
        weekday = None
        if weekday_raw:
            try:
                weekday = WEEKDAYS_NUMBER[weekday_raw.upper()]
            except KeyError:
                pass

        start_time = parse_time(row.get("time_start") or row.get("stime"))
        end_time = parse_time(row.get("time_end") or row.get("etime"))

        schedule = Schedule.objects.create(
            weekday=weekday or 1,
            room=room,
            faculty=faculty,
            start_time=start_time,
            end_time=end_time,
        )

        start_date = parse_date(row.get("sts"))
        end_date = parse_date(row.get("ets"))

        Section.objects.create(
            course=course,
            semester=semester,
            number=section_no,
            start_date=start_date,
            end_date=end_date,
            schedule=schedule,
            max_seats=_parse_int(row.get("max_seats")) or 30,
        )
