"""Helpers to import section data from CSV.

This module provides :func:`populate_sections_from_csv` which creates the
fundamental timetable objects (academic years, semesters, courses, instructors,
sessions and sections) from a CSV stream.  It is designed for seeding an empty
database using the exported ``cleaned_tscc.csv`` file.
"""

from __future__ import annotations


def parse_int(value: str | None) -> int | None:
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

import csv
from datetime import date
from app.academics.models import College, Course
from app.timetable.models import AcademicYear, Semester, Section, Session


def populate_sections_from_csv(cmd, csv_stream) -> None:
    """Create Sections and related objects from a CSV stream."""
    reader = csv.DictReader(csv_stream)
    for row in reader:
        college_code = row.get("college", "").strip()
        course_code = row.get("course", "").strip()
        semester_code = row.get("semester", "").strip()
        number = parse_int(row.get("number")) or 1
        instructor_id = parse_int(row.get("instructor"))
        room_id = parse_int(row.get("room"))
        max_seats = parse_int(row.get("max_seats")) or 30

        college, _ = College.objects.get_or_create(
            code=college_code, defaults={"long_name": college_code}
        )
        dept = "".join(c for c in course_code if c.isalpha())
        num = "".join(c for c in course_code if c.isdigit())
        course, _ = Course.objects.get_or_create(
            name=dept,
            number=num,
            defaults={"title": dept, "college": college, "code": f"{dept}{num}"},
        )

        year_part, sem_part = semester_code.split("_Sem")
        start_year = 2000 + int(year_part.split("-")[0])
        ay, _ = AcademicYear.objects.get_or_create(start_date=date(start_year, 1, 1))
        semester, _ = Semester.objects.get_or_create(
            academic_year=ay,
            number=int(sem_part),
            defaults={"start_date": ay.start_date, "end_date": ay.start_date},
        )

        section = Section.objects.create(
            semester=semester,
            course=course,
            number=number,
            faculty_id=instructor_id,
            start_date=semester.start_date,
            end_date=semester.end_date,
            max_seats=max_seats,
        )
        if room_id:
            Session.objects.create(section=section, room_id=room_id)
