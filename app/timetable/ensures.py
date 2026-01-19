"""Shared fast lookup helpers for timetable imports."""

from __future__ import annotations

from datetime import date, time
from typing import Dict, Optional, Tuple

from app.academics.models.course import CurriculumCourse
from app.shared.types import (
    RoomCacheT,
    RoomKeyT,
    ScheduleCacheT,
    ScheduleKeyT,
    SectionKeyMapT,
    SessionCacheT,
    SessionKeyT,
    TwoStrIntMapT,
)
from app.shared.utils import parse_str, to_int
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.schedule import Schedule
from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.timetable.models.session import SecSession
from app.spaces.models.core import Room, Space
from app.timetable.utils import normalize_academic_year, parse_semester_code

# Simple in-memory caches keyed by normalized tokens
SEMESTER_CACHE: Dict[Tuple[str, int], Semester] = {}
SECTION_CACHE: Dict[Tuple[int, int, int, Optional[int]], Section] = {}
SEMESTER_ID_CACHE: TwoStrIntMapT = {}
SECTION_ID_CACHE: SectionKeyMapT = {}
SCHEDULE_ID_CACHE: ScheduleCacheT = {}
ROOM_ID_CACHE: RoomCacheT = {}
SESSION_ID_CACHE: SessionCacheT = {}


def _section_cache_key(
    semester_id: int, curriculum_course_id: int, number: int
) -> Tuple[int, int, int, Optional[int]]:
    """Build a cache key for section lookups."""
    # it is ok, it as if I saved in a var.
    return (semester_id, curriculum_course_id, number, None)


def _normalize_semester_key(
    academic_year: str, semester_no: str | int, default: str | None = None
) -> Tuple[str, int]:
    """Normalize semester inputs to a cache key."""
    def_ay, def_sem = parse_semester_code(default)

    ay_code = normalize_academic_year(academic_year or def_ay)

    _sem_int = to_int(semester_no)
    sem_no = _sem_int if _sem_int else def_sem

    return ay_code, sem_no


def _prime_semester_id_cache() -> None:
    """Load semester ids into the local cache if empty."""
    if SEMESTER_ID_CACHE:
        return
    for ay_code, sem_no, pk in Semester.objects.values_list(
        "academic_year__code", "number", "id"
    ):
        SEMESTER_ID_CACHE[(ay_code, sem_no)] = pk


def _prime_schedule_id_cache() -> None:
    """Load schedule ids into the local cache if empty."""
    if SCHEDULE_ID_CACHE:
        return
    for weekday, start, end, pk in Schedule.objects.values_list(
        "weekday", "start_time", "end_time", "id"
    ):
        SCHEDULE_ID_CACHE[(weekday, start, end)] = pk


def _prime_room_id_cache() -> None:
    """Load room ids into the local cache if empty."""
    if ROOM_ID_CACHE:
        return
    for space_code, room_code, pk in Room.objects.values_list(
        "space__code", "code", "id"
    ):
        ROOM_ID_CACHE[(space_code, room_code)] = pk


def _prime_session_id_cache() -> None:
    """Load session ids into the local cache if empty."""
    if SESSION_ID_CACHE:
        return
    for section_id, schedule_id, pk, room_id in SecSession.objects.values_list(
        "section_id", "schedule_id", "id", "room_id"
    ):
        SESSION_ID_CACHE[(section_id, schedule_id)] = (pk, room_id)


def ensure_academic_year_code(code: str | None) -> AcademicYear:
    """Look up or auto-create an AcademicYear from its 'YY-YY' code.

    If no code return current AcademicYear, the code should be properly formated.
    """
    code = parse_str(code)
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
    ay_code, sem_no = _normalize_semester_key(academic_year, semester_no, default)

    key = (ay_code, sem_no)
    cached = SEMESTER_CACHE.get(key)

    if cached:
        SEMESTER_ID_CACHE[key] = cached.id
        return cached

    semester, _ = Semester.objects.get_or_create(
        academic_year=ensure_academic_year_code(ay_code), number=sem_no
    )

    SEMESTER_CACHE[key] = semester
    SEMESTER_ID_CACHE[key] = semester.id
    return semester


def ensure_semester_code(code: str | None) -> Semester:
    """Look-up Semester object from a semester code like '25-26_Sem2'."""
    ay_code, sem_no = parse_semester_code(code)
    return ensure_semester(ay_code, sem_no)


def ensure_semester_id(
    academic_year: str, semester_no: str | int, default: str | None = None
) -> int:
    """Return a Semester id for the given academic year and semester."""
    ay_code, sem_no = _normalize_semester_key(academic_year, semester_no, default)
    key = (ay_code, sem_no)
    _prime_semester_id_cache()
    cached = SEMESTER_ID_CACHE.get(key)
    if cached:
        return cached
    semester = ensure_semester(ay_code, sem_no)
    return semester.id


def ensure_section(
    semester: Semester,
    curriculum_course: CurriculumCourse,
    number: int,
    faculty_id: int | None = None,
) -> Section:
    """Look-up or autocreate a Section."""
    key = _section_cache_key(semester.id, curriculum_course.id, number)
    cached = SECTION_CACHE.get(key)
    if cached:
        if faculty_id and cached.faculty_id is None:
            cached.faculty_id = faculty_id
            cached.save(update_fields=["faculty_id"])
        SECTION_ID_CACHE[key] = cached.id
        return cached
    sec, _ = Section.objects.get_or_create(
        semester=semester,
        curriculum_course=curriculum_course,
        number=number,
        defaults={"faculty_id": faculty_id},
    )
    if faculty_id and sec.faculty_id is None:
        sec.faculty_id = faculty_id
        sec.save(update_fields=["faculty_id"])
    SECTION_CACHE[key] = sec
    SECTION_ID_CACHE[key] = sec.id
    return sec


def ensure_section_id(
    semester_id: int,
    curriculum_course_id: int,
    number: int,
    faculty_id: int | None = None,
) -> int:
    """Return a Section id for the given identifiers."""
    key = _section_cache_key(semester_id, curriculum_course_id, number)
    cached = SECTION_CACHE.get(key)
    if cached:
        if faculty_id and cached.faculty_id is None:
            cached.faculty_id = faculty_id
            cached.save(update_fields=["faculty_id"])
        SECTION_ID_CACHE[key] = cached.id
        return cached.id
    cached_id = SECTION_ID_CACHE.get(key)
    if cached_id:
        if faculty_id:
            Section.objects.filter(id=cached_id, faculty_id__isnull=True).update(
                faculty_id=faculty_id
            )
        return cached_id
    sec, _ = Section.objects.get_or_create(
        semester_id=semester_id,
        curriculum_course_id=curriculum_course_id,
        number=number,
        defaults={"faculty_id": faculty_id},
    )
    if faculty_id and sec.faculty_id is None:
        sec.faculty_id = faculty_id
        sec.save(update_fields=["faculty_id"])
    SECTION_CACHE[key] = sec
    SECTION_ID_CACHE[key] = sec.id
    return sec.id


def ensure_schedule_id(weekday: int, start_time: time, end_time: time | None) -> int:
    """Return a Schedule id for the given weekday/time values."""
    key: ScheduleKeyT = (weekday, start_time, end_time)
    _prime_schedule_id_cache()
    cached = SCHEDULE_ID_CACHE.get(key)
    if cached:
        return cached
    schedule, _ = Schedule.objects.get_or_create(
        weekday=weekday,
        start_time=start_time,
        end_time=end_time,
    )
    SCHEDULE_ID_CACHE[key] = schedule.id
    return schedule.id


def ensure_room_id(space_code: str, room_code: str) -> int:
    """Return a Room id for the given space/room codes."""
    key: RoomKeyT = (space_code or "TBA", room_code or "TBA")
    _prime_room_id_cache()
    cached = ROOM_ID_CACHE.get(key)
    if cached:
        return cached
    if key[0] == "TBA":
        space = Space.get_default()
    else:
        space, _ = Space.objects.get_or_create(
            code=key[0],
            defaults={"full_name": key[0]},
        )
    room, _ = Room.objects.get_or_create(space=space, code=key[1])
    ROOM_ID_CACHE[key] = room.id
    return room.id


def ensure_session_id(
    section_id: int,
    schedule_id: int,
    room_id: int | None = None,
    *,
    create: bool = True,
) -> tuple[int, int] | None:
    """Return a SecSession id for the given identifiers.

    Args:
        section_id: Section id for the session.
        schedule_id: Schedule id for the session.
        room_id: Room id required when create is True.
        create: When True, create the session if it does not exist.

    Returns:
        Tuple of (session_id, room_id), or None when not found and create=False.

    Raises:
        ValueError: When create=True and room_id is missing.
    """
    key: SessionKeyT = (section_id, schedule_id)
    _prime_session_id_cache()
    cached = SESSION_ID_CACHE.get(key)
    if cached:
        return cached

    if not create:
        return None

    if room_id is None:
        raise ValueError("room_id is required to create a session")

    defaults: dict[str, int] = {"room_id": room_id}
    session, _ = SecSession.objects.get_or_create(
        section_id=section_id,
        schedule_id=schedule_id,
        defaults=defaults,
    )
    if room_id is not None and session.room_id != room_id:
        session.room_id = room_id
        session.save(update_fields=["room_id"])
    SESSION_ID_CACHE[key] = (session.id, session.room_id)
    return SESSION_ID_CACHE[key]
