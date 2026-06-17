"""Typed shapes for faculty grade-entry services."""

from __future__ import annotations

from typing import TypedDict

from app.people.models.student import Student
from app.registry.models.grade import Grade
from app.timetable.models.section import Section


class FacultySectionRowT(TypedDict):
    """One assigned section row displayed to faculty."""

    section: Section
    course_code: str
    course_title: str
    roster_count: int
    pending_count: int
    grade_entry_open: bool
    roster_url: str
    download_url: str


class FacultyGradeRowT(TypedDict):
    """One student grade row displayed in a faculty roster."""

    grade: Grade
    student: Student
    student_label: str
    student_id: str
    current_code: str


__all__ = ["FacultyGradeRowT", "FacultySectionRowT"]
