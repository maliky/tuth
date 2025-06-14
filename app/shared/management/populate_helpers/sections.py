"""Helpers to import section data from CSV.

This module provides :func:`populate_sections_from_csv` which creates the
fundamental timetable objects (academic years, semesters, courses, instructors,
sessions and sections) from a CSV stream.  It is designed for seeding an empty
database using the exported ``cleaned_tscc.csv`` file.
"""

from __future__ import annotations

import csv
from datetime import date
from typing import TextIO

from django.contrib.auth import get_user_model

from app.academics.models.college import College
from app.academics.models.course import Course
from app.spaces.models import Room
from app.timetable.models import AcademicYear, Semester, Section
from app.shared.management.populate_helpers.utils import log


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


def populate_sections_from_csv(cmd, csv_file: TextIO) -> None:
    """Create Section records from a CSV stream.

    Parameters
    ----------
    cmd:
        Management command used for logging.
    csv_file:
        File-like object yielding CSV rows with columns ``college``, ``course``,
        ``semester``, ``number``, ``instructor``, ``room`` and ``max_seats``.

    The function creates any missing ``College``, ``Course``, ``AcademicYear``
    and ``Semester`` records. ``Faculty`` profiles are auto-created when an
    instructor id is provided. New ``Section`` rows are inserted for each CSV
    line.
    """

    reader = csv.DictReader(csv_file)

    for row in reader:
        # skip blank rows
        if not any((value or '').strip() for value in row.values()):
            continue

        college_code = (row.get('college') or 'COAS').strip().upper()
        college, _ = College.objects.get_or_create(code=college_code)

        # --- course ---------------------------------------------------------
        course_token = (row.get('course') or '').strip().upper()
        dept = ''.join(ch for ch in course_token if ch.isalpha())
        num = ''.join(ch for ch in course_token if ch.isdigit())
        course, _ = Course.objects.get_or_create(
            name=dept,
            number=num,
            college=college,
            defaults={'title': course_token or f'{dept}{num}'},
        )

        # --- semester ------------------------------------------------------
        sem_val = (row.get('semester') or '').strip()
        ay_part, _, sem_no_part = sem_val.partition('_Sem')
        sem_no = parse_int(sem_no_part) or 1
        start_year = 2000 + int(ay_part.split('-')[0])

        ay, _ = AcademicYear.objects.get_or_create(
            code=ay_part,
            defaults={'start_date': date(start_year, 8, 1)},
        )
        semester, _ = Semester.objects.get_or_create(
            academic_year=ay,
            number=sem_no,
        )

        sec_no = parse_int(row.get('number')) or 1
        max_seats = parse_int(row.get('max_seats')) or 30

        faculty_id = parse_int(row.get('instructor'))
        faculty = None
        if faculty_id is not None:
            from app.people.models.profiles import Staff, Faculty

            faculty = Faculty.objects.filter(pk=faculty_id).first()
            if faculty is None:
                User = get_user_model()
                user = User.objects.filter(pk=faculty_id).first()
                if user:
                    staff, _ = Staff.objects.get_or_create(
                        user=user,
                        defaults={'staff_id': f'TU-{user.id}', 'phone': '000'},
                    )
                    faculty, _ = Faculty.objects.get_or_create(
                        staff_profile=staff,
                        defaults={'college': college},
                    )
        room_id = parse_int(row.get('room'))
        room = Room.objects.filter(pk=room_id).first() if room_id else None

        section = Section.objects.create(
            semester=semester,
            course=course,
            number=sec_no,
            faculty=faculty,
            max_seats=max_seats,
        )

        if room:
            from datetime import time
            from app.timetable.models import Session, Schedule

            sched, _ = Schedule.objects.get_or_create(
                weekday=0,
                start_time=time(0, 0),
            )
            Session.objects.create(room=room, schedule=sched, section=section)

        log(cmd, f"Created section {section.short_code}", style='SUCCESS')
