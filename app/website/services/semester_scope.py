"""Career-aware semester filters for staff portal views."""

from __future__ import annotations

from datetime import date

from django.db.models import QuerySet

from app.academics.career_scope import CAREER_ALL, CareerModeT
from app.academics.choices import AcademicCareer
from app.timetable.models.semester import Semester

GRADUATE_SEMESTER_FLOOR = date(2026, 8, 1)


def is_graduate_semester_floor_active() -> bool:
    """Return whether the graduate-only semester floor can be enforced."""
    return Semester.objects.filter(
        academic_career=AcademicCareer.GRADUATE,
        academic_year__start_date__gte=GRADUATE_SEMESTER_FLOOR,
    ).exists()


def should_apply_graduate_semester_floor(career: CareerModeT) -> bool:
    """Return whether a view should hide pre-graduate-launch semesters."""
    return career == AcademicCareer.GRADUATE.value and is_graduate_semester_floor_active()


def semester_queryset_for_career(
    career: CareerModeT,
    queryset: QuerySet[Semester] | None = None,
) -> QuerySet[Semester]:
    """Return semesters visible for the selected academic career."""
    semesters = queryset or Semester.objects.select_related("academic_year")
    if career != CAREER_ALL:
        semesters = semesters.filter(academic_career=career)
    if should_apply_graduate_semester_floor(career):
        return semesters.filter(academic_year__start_date__gte=GRADUATE_SEMESTER_FLOOR)
    return semesters


def filter_by_career_semester_floor(
    queryset: QuerySet,
    semester_path: str,
    career: CareerModeT,
) -> QuerySet:
    """Filter any queryset by the graduate semester launch floor."""
    if should_apply_graduate_semester_floor(career):
        return queryset.filter(
            **{
                f"{semester_path}__academic_year__start_date__gte": (
                    GRADUATE_SEMESTER_FLOOR
                )
            }
        )
    return queryset


__all__ = [
    "GRADUATE_SEMESTER_FLOOR",
    "filter_by_career_semester_floor",
    "semester_queryset_for_career",
    "should_apply_graduate_semester_floor",
]
