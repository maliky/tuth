"""Shared fast lookup helpers for timetable imports."""

from typing import Dict, Optional, Tuple

from app.academics.models.course import CurriculumCourse
from app.timetable.admin.core_widgets import ensure_academic_year_code
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.timetable.utils import normalize_academic_year

# Simple in-memory caches keyed by normalized tokens
SEMESTER_CACHE: Dict[Tuple[str, int], Semester] = {}
SECTION_CACHE: Dict[Tuple[int, int, int, Optional[int]], Section] = {}


def ensure_semester(academic_year: str, semester_no: str | int) -> Semester:
    ay_code = normalize_academic_year(academic_year) or ""
    sem_no = int(float(semester_no)) if semester_no not in (None, "") else 0
    key = (ay_code, sem_no)
    cached = SEMESTER_CACHE.get(key)
    if cached:
        return cached
    ay_obj = ensure_academic_year_code(ay_code) if ay_code else None
    semester, _ = Semester.objects.get_or_create(
        academic_year=ay_obj,
        number=sem_no,
    )
    SEMESTER_CACHE[key] = semester
    return semester


def ensure_section(
    semester: Semester,
    curriculum_course: CurriculumCourse,
    number: int,
    faculty_id: int | None = None,
) -> Section:
    key = (semester.id, curriculum_course.id, number, faculty_id)
    cached = SECTION_CACHE.get(key)
    if cached:
        return cached
    sec, _ = Section.objects.get_or_create(
        semester=semester,
        curriculum_course=curriculum_course,
        number=number,
        faculty_id=faculty_id,
    )
    SECTION_CACHE[key] = sec
    return sec
