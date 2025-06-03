"""From csv module."""

from __future__ import annotations

from csv import DictReader
from datetime import date
from pathlib import Path
from typing import IO

from django.contrib.auth.models import User
from django.db import transaction

from app.academics.admin.widgets import CourseWidget, CollegeWidget
from app.academics.models import College, Course, Curriculum, CurriculumCourse
from app.shared.constants import TEST_PW
from app.shared.management.populate_helpers.utils import log
from app.spaces.models import Room
from app.timetable.admin.widgets import SemesterWidget
from app.timetable.models import Section, Semester

# widgets = encapsulated creation logic & regex parsing
cw = CourseWidget(model=Course, field="code")
clg_widget = CollegeWidget(model=College, field="code")


@transaction.atomic
def populate_curricula_from_csv(cmd, csv_path: Path | str | IO[str]) -> None:
    """
    Reads *csv_path* and guarantees each Curriculum and its lines exist.

    *cmd*  is the calling management-command instance (for coloured output).
    Helper to bulk-create Curriculum rows (plus on-the-fly Colleges / Courses)
    from a CSV file.

    Expected CSV headers  (case-sensitive)
    ──────────────────────────────────────
    short_name,long_name,college,list_courses

    • **short_name**  ─ mandatory ─ unique key for Curriculum
    • **long_name**   ─ optional  ─ defaults to short_name
    • **college**     ─ mandatory ─ College.code  (auto-created if absent)
    • **list_courses**─ mandatory ─ semicolon list of course codes
                                 (same regex as COURSE_PATTERN)

    Usage inside any management command
    ───────────────────────────────────
    from app.shared.management.populate_helpers import (
        populate_curricula_from_csv,
        log,
    )

    log(cmd, "⚙  Curricula")
    populate_curricula_from_csv(cmd, Path("Seed_data/curricula.csv"))
    """
    # accept file-like objects (unit-tests) or paths
    if isinstance(csv_path, (str, Path)):
        fh: IO[str] = open(csv_path, newline="", encoding="utf-8")
        auto_close = True
    else:
        fh = csv_path
        auto_close = False

    created, updated, skipped = 0, 0, 0
    with fh:
        for row in DictReader(fh):
            if (
                not row.get("short_name")
                or not row.get("college")
                or not row.get("list_courses")
            ):
                log(cmd, f"  ⚠  Incomplete row skipped: {row}", style="WARNING")
                skipped += 1
                continue

            # ─── resolve / create FK objects ────────────────────────────────
            college = clg_widget.clean(row["college"], row)
            assert (
                college is not None
            ), "populate_curricula_from_csv(): college cannot be None"

            short_name = row["short_name"].strip()
            long_name = (row.get("long_name") or short_name).strip()

            cur, cur_created = Curriculum.objects.get_or_create(
                short_name=short_name,
                defaults=dict(
                    title=long_name, college=college, creation_date=date.today()
                ),
            )

            if not cur_created and cur.college_id != college.id:
                log(
                    cmd,
                    f"  ⚠  Curriculum {short_name} ignored (college mismatch "
                    f"{cur.college.code} ≠ {college.code})",
                    style="WARNING",
                )
                skipped += 1
                continue

            # ─── parse course list ───────────────────────────────────────────
            codes = [t.strip() for t in row["list_courses"].split(";") if t.strip()]
            lines_added = 0
            for token in codes:
                course = cw.clean(token, row)
                _, made_line = CurriculumCourse.objects.get_or_create(
                    curriculum=cur, course=course
                )
                lines_added += int(made_line)

            # counting
            if cur_created:
                created += 1
            elif lines_added:
                updated += 1

    log(
        cmd,
        f"  ↳ {created} curricula created, {updated} updated, {skipped} rows skipped",
    )
    if auto_close:
        fh.close()


def populate_sections_from_csv(cmd, csv_path: Path | str | IO[str]) -> None:
    """
    Read *csv_path* and guarantee every row exists as a Section.

    *cmd* is the calling management-command instance so we can
    write coloured output with the shared ``log`` helper.
    Helper to bulk-create Section rows from a CSV file.

    Expected CSV headers  (case-sensitive)
    ──────────────────────────────────────
    college,course,semester,number,faculty,room,max_seats

    • **college**   ─ mandatory  ─ College.code  (e.g. COAS)
    • **course**    ─ mandatory  ─ Course.code   (e.g. MATH101)
    • **semester**  ─ mandatory  ─ “YY-YY_SemN” (e.g. 24-25_Sem1)
    • **number**    ─ optional   ─ if blank/0 the autoincrement signal fills it
    • **faculty** / **room**  ─
    • **max_seats** ─ optional   ─ defaults to 30

    Usage inside any management command
    ───────────────────────────────────
    from app.shared.management.populate_helpers import (
        populate_sections_from_csv,
        log,
    )

    log(cmd, "⚙  Sections")          # headline
    populate_sections_from_csv(cmd, Path("seed/sections.csv"))
    """
    cw = CourseWidget(model=Course, field="code")
    sw = SemesterWidget(model=Semester, field="id")

    # accept a file-like object (for tests) or a path
    if isinstance(csv_path, (str, Path)):
        fh: IO[str]
        fh = open(csv_path, newline="", encoding="utf-8")
        auto_close = True
    else:
        fh = csv_path
        auto_close = False

    created = 0
    skipped = 0
    with fh:
        for row in DictReader(fh):
            if not row.get("course") or not row.get("semester") or not row.get("college"):
                log(cmd, f"  ⚠  Incomplete row skipped: {row}", style="WARNING")
                skipped += 1
                continue

            course = cw.clean(row["course"], row)
            semester = sw.clean(row["semester"], row)

            number_raw = row.get("number") or ""
            number_int = int(number_raw.strip()) if number_raw.strip().isdigit() else None

            faculty_raw = (row.get("faculty") or "").strip()
            faculty_id = None
            if faculty_raw:
                faculty_obj, _ = User.objects.get_or_create(
                    username=faculty_raw,
                    defaults={"password": TEST_PW},
                )
                faculty_id = faculty_obj.id

            room_raw = (row.get("room") or "").strip()
            room_id = None
            if room_raw:
                if room_raw.isdigit() and Room.objects.filter(pk=int(room_raw)).exists():
                    room_id = int(room_raw)
                else:
                    room_obj, _ = Room.objects.get_or_create(name=room_raw)
                    room_id = room_obj.id

            max_seats_raw = row.get("max_seats") or ""
            max_seats = (
                int(max_seats_raw.strip()) if max_seats_raw.strip().isdigit() else 30
            )

            sec, made = Section.objects.get_or_create(
                course=course,
                semester=semester,
                number=number_int,  # None → autoincrement signal
                defaults={
                    "faculty_id": faculty_id,
                    "room_id": room_id,
                    "max_seats": max_seats,
                },
            )
            created += int(made)

    log(cmd, f"  ↳ {created} sections added, {skipped} rows skipped")
    if auto_close:
        fh.close()
