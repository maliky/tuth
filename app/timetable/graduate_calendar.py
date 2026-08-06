"""Graduate academic calendar helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

from app.academics.choices import AcademicCareer
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester, SemesterStatus


@dataclass(frozen=True)
class GraduateSemesterSpec:
    """One graduate semester that should exist for launch."""

    academic_year_start: date
    number: int
    start_date: date
    end_date: date
    status_id: str


GRADUATE_COURSE_WINDOW_YEAR_STARTS: Final[tuple[date, ...]] = (
    date(2026, 8, 1),
    date(2027, 8, 1),
)
GRADUATE_SEMESTER_SPECS: Final[tuple[GraduateSemesterSpec, ...]] = (
    GraduateSemesterSpec(
        date(2026, 8, 1),
        1,
        date(2026, 8, 1),
        date(2027, 1, 31),
        "registration",
    ),
    GraduateSemesterSpec(
        date(2026, 8, 1),
        2,
        date(2027, 2, 1),
        date(2027, 7, 31),
        "planning",
    ),
    GraduateSemesterSpec(
        date(2027, 8, 1),
        1,
        date(2027, 8, 1),
        date(2028, 1, 31),
        "planning",
    ),
    GraduateSemesterSpec(
        date(2027, 8, 1),
        2,
        date(2028, 2, 1),
        date(2028, 7, 31),
        "planning",
    ),
)


def ensure_graduate_semesters() -> list[tuple[Semester, bool]]:
    """Create or update the launch graduate semesters."""
    SemesterStatus._populate_attributes_and_db()
    Semester.objects.filter(
        academic_career=AcademicCareer.GRADUATE,
        status_id=Semester.REGISTRATION_OPEN_CODES,
    ).update(status_id="planning")
    rows: list[tuple[Semester, bool]] = []
    for spec in GRADUATE_SEMESTER_SPECS:
        academic_year, _created_year = AcademicYear.objects.get_or_create(
            start_date=spec.academic_year_start
        )
        semester, created = Semester.objects.get_or_create(
            academic_year=academic_year,
            number=spec.number,
            academic_career=AcademicCareer.GRADUATE,
            defaults={
                "start_date": spec.start_date,
                "end_date": spec.end_date,
                "status_id": spec.status_id,
            },
        )
        if not created:
            semester.start_date = spec.start_date
            semester.end_date = spec.end_date
            semester.status_id = spec.status_id
            semester.save(update_fields=["start_date", "end_date", "status"])
        rows.append((semester, created))
    return rows


__all__ = [
    "GRADUATE_COURSE_WINDOW_YEAR_STARTS",
    "GRADUATE_SEMESTER_SPECS",
    "GraduateSemesterSpec",
    "ensure_graduate_semesters",
]
