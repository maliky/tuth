"""Shared fast lookup helpers for timetable imports."""

from datetime import date
from typing import Dict, Optional, Tuple

from app.academics.models.course import CurriculumCourse
from app.shared.utils import to_int
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.timetable.utils import normalize_academic_year, parse_semester_code

# Simple in-memory caches keyed by normalized tokens
SEMESTER_CACHE: Dict[Tuple[str, int], Semester] = {}
SECTION_CACHE: Dict[Tuple[int, int, int, Optional[int]], Section] = {}


def ensure_academic_year_code(code: str | None) -> AcademicYear:
    """Look up or auto-create an AcademicYear from its 'YY-YY' code.

    If no code return current AcademicYear, the code should be properly formated.
    """
    code = (code or "").strip()
    if not code:
        return AcademicYear.get_default()

    ys, _ = code.split("-")
    start = date(int("20" + ys), 9, 1)

    ay_obj, _created = AcademicYear.objects.get_or_create(
        code=code, defaults={"start_date": start}
    )

    if _created:  # > is this really necessary ?
        ay_obj.save()

    return ay_obj


def ensure_semester(
    academic_year: str, semester_no: str | int, default: str | None = None
) -> Semester:
    """Look-up Semester object from an academics_year and semester_no.

    Falls back to a defined default semester when code such as '25-26_Sem2' exists,
    else get the semester 0 for the current academic year.
    """
    def_ay, def_sem = parse_semester_code(default)

    ay_code = normalize_academic_year(academic_year or def_ay)

    _sem_int = to_int(semester_no)
    sem_no = _sem_int if _sem_int else def_sem

    key = (ay_code, sem_no)
    cached = SEMESTER_CACHE.get(key)

    if cached:
        return cached

    semester, _ = Semester.objects.get_or_create(
        academic_year=ensure_academic_year_code(ay_code), number=sem_no
    )

    SEMESTER_CACHE[key] = semester
    return semester


def ensure_section(
    semester: Semester,
    curriculum_course: CurriculumCourse,
    number: int,
    faculty_id: int | None = None,
) -> Section:
    """Look-up or autocreate a Section."""
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
