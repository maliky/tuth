# app/shared/management/populate_helpers/sections.py
"""
Helper to bulk-create Section rows from a CSV file.

Expected CSV headers  (case-sensitive)
──────────────────────────────────────
college,course,semester,number,instructor,room,max_seats

• **college**   ─ mandatory  ─ College.code  (e.g. COAS)
• **course**    ─ mandatory  ─ Course.code   (e.g. MATH101)
• **semester**  ─ mandatory  ─ “YY-YY_SemN” (e.g. 24-25_Sem1)
• **number**    ─ optional   ─ if blank/0 the autoincrement signal fills it
• **instructor** / **room**  ─ 
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

from __future__ import annotations
from csv import DictReader
from pathlib import Path
from typing import IO

from app.shared.management.populate_helpers.utils import log
from app.timetable.models import Section
from app.timetable.admin.widgets import (
    CourseWidget,
    SemesterWidget,
)
from app.academics.models import Course
from app.timetable.models import Semester


def populate_sections_from_csv(cmd, csv_path: Path | str | IO[str]) -> None:
    """
    Read *csv_path* and guarantee every row exists as a Section.

    *cmd* is the calling management-command instance so we can
    write coloured output with the shared ``log`` helper.
    """
    cw = CourseWidget(Course, "code")
    sw = SemesterWidget(Semester, "id")

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
            number_int = int(number_raw) if number_raw.strip().isdigit() else None

            sec, made = Section.objects.get_or_create(
                course=course,
                semester=semester,
                number=number_int,  # None → autoincrement signal
                defaults={
                    "instructor_id": row.get("instructor") or None,
                    "room_id": row.get("room") or None,
                    "max_seats": int(row.get("max_seats") or 30),
                },
            )
            created += int(made)

    log(cmd, f"  ↳ {created} sections added, {skipped} rows skipped")
    if auto_close:
        fh.close()
