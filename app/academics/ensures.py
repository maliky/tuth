"""Shared fast lookup helpers for academic imports."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from app.academics.choices import COLLEGE_LONG_NAME
from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriCourse
from app.academics.models.department import Department
from app.academics.utils import normalize_college_code, normalize_dpt_code
from app.shared.models import CreditHour
from app.shared.types import DeptCollegeMapT, DeptCourseMapT, StrIntMapT, TwoIntIntMapT
from app.shared.utils import parse_str

COLLEGE_CACHE: Dict[str, College] = {}
DEPARTMENT_CACHE: Dict[Tuple[str, int], Department] = {}
COURSE_CACHE: Dict[Tuple[int, str], Course] = {}
CURRICULUM_CACHE: Dict[Tuple[str, Optional[int]], Curriculum] = {}
CURRICULUM_COURSE_CACHE: Dict[Tuple[int, int], CurriCourse] = {}
CREDIT_HOUR_CACHE: Dict[int, CreditHour] = {}

COLLEGE_ID_CACHE: StrIntMapT = {}
COLLEGE_BY_ID_CACHE: Dict[int, College] = {}
DEPARTMENT_ID_CACHE: DeptCollegeMapT = {}
DEPARTMENT_BY_ID_CACHE: Dict[int, Department] = {}
COURSE_ID_CACHE: DeptCourseMapT = {}
COURSE_BY_ID_CACHE: Dict[int, Course] = {}
CURRICULUM_ID_CACHE: StrIntMapT = {}
CURRICULUM_BY_ID_CACHE: Dict[int, Curriculum] = {}
CURRICULUM_COURSE_ID_CACHE: TwoIntIntMapT = {}


def _normalize_crs_no(value: str) -> str:
    """Normalize course numbers like '101.0' -> '101'."""
    # This should not happen but taking care of 102.0 -> 102.
    value = parse_str(value)
    if value.endswith(".0"):
        value = value[:-2]
    return value


def _prime_college_id_cache() -> None:
    """Load college ids into the local cache if empty."""
    if COLLEGE_ID_CACHE:
        return
    for code, pk in College.objects.values_list("code", "id"):
        COLLEGE_ID_CACHE[code.lower()] = pk


def _prime_dpt_id_cache() -> None:
    """Load department ids into the local cache if empty."""
    if DEPARTMENT_ID_CACHE:
        return
    for code, college_id, pk in Department.objects.values_list(
        "code", "college_id", "id"
    ):
        DEPARTMENT_ID_CACHE[(code.upper(), college_id)] = pk


def _prime_crs_id_cache() -> None:
    """Load course ids into the local cache if empty."""
    if COURSE_ID_CACHE:
        return
    for department_id, number, pk in Course.objects.values_list(
        "department_id", "number", "id"
    ):
        COURSE_ID_CACHE[(department_id, str(number))] = pk


def _prime_curri_id_cache() -> None:
    """Load curriculum ids into the local cache if empty."""
    if CURRICULUM_ID_CACHE:
        return
    for name, pk in Curriculum.objects.values_list("short_name", "id"):
        CURRICULUM_ID_CACHE[parse_str(name, "lower")] = pk


def _prime_curri_crs_id_cache() -> None:
    """Load curriculum course ids into the local cache if empty."""
    if CURRICULUM_COURSE_ID_CACHE:
        return
    for curriculum_id, course_id, pk in CurriCourse.objects.values_list(
        "curriculum_id", "course_id", "id"
    ):
        CURRICULUM_COURSE_ID_CACHE[(curriculum_id, course_id)] = pk


def _get_college_by_id(college_id: int) -> College:
    """Fetch a college by id and keep caches aligned."""
    cached = COLLEGE_BY_ID_CACHE.get(college_id)
    if cached:
        return cached
    college = College.objects.get(pk=college_id)
    COLLEGE_BY_ID_CACHE[college_id] = college
    COLLEGE_CACHE[college.code] = college
    COLLEGE_ID_CACHE[college.code.lower()] = college.id
    return college


def _get_dpt_by_id(department_id: int) -> Department:
    """Fetch a department by id and keep caches aligned."""
    cached = DEPARTMENT_BY_ID_CACHE.get(department_id)
    if cached:
        return cached
    dept = Department.objects.get(pk=department_id)
    DEPARTMENT_BY_ID_CACHE[department_id] = dept
    DEPARTMENT_CACHE[(dept.code, dept.college_id)] = dept
    DEPARTMENT_ID_CACHE[(dept.code, dept.college_id)] = dept.id
    return dept


def _get_crs_by_id(course_id: int) -> Course:
    """Fetch a course by id and keep caches aligned."""
    cached = COURSE_BY_ID_CACHE.get(course_id)
    if cached:
        return cached
    course = Course.objects.get(pk=course_id)
    COURSE_BY_ID_CACHE[course_id] = course
    COURSE_CACHE[(course.department_id, course.number)] = course
    COURSE_ID_CACHE[(course.department_id, course.number)] = course.id
    return course


def _get_curri_by_id(curriculum_id: int) -> Curriculum:
    """Fetch a curriculum by id and keep caches aligned."""
    cached = CURRICULUM_BY_ID_CACHE.get(curriculum_id)
    if cached:
        return cached
    curriculum = Curriculum.objects.get(pk=curriculum_id)
    CURRICULUM_BY_ID_CACHE[curriculum_id] = curriculum
    CURRICULUM_CACHE[(curriculum.short_name.lower(), curriculum.college_id)] = curriculum
    CURRICULUM_ID_CACHE[curriculum.short_name.lower()] = curriculum.id
    return curriculum


def ensure_college(code_raw: str) -> College:
    """Return the college attached to code_raw if possible cached."""
    code = normalize_college_code(code_raw)
    cached = COLLEGE_CACHE.get(code)

    if cached:
        COLLEGE_ID_CACHE[code.lower()] = cached.id
        COLLEGE_BY_ID_CACHE[cached.id] = cached
        return cached

    college, _ = College.objects.get_or_create(
        code=code,
        defaults={"long_name": COLLEGE_LONG_NAME.get(code.lower(), code)},
    )
    COLLEGE_CACHE[code] = college
    COLLEGE_ID_CACHE[code.lower()] = college.id
    COLLEGE_BY_ID_CACHE[college.id] = college
    return college


def ensure_dpt(dept_code_raw: str, college: College) -> Department:
    """Return a department for the given dept_code and college."""
    dept_code = normalize_dpt_code(dept_code_raw)
    key = (dept_code, college.id)
    cached = DEPARTMENT_CACHE.get(key)
    if cached:
        DEPARTMENT_ID_CACHE[key] = cached.id
        DEPARTMENT_BY_ID_CACHE[cached.id] = cached
        return cached
    dept, _ = Department.objects.get_or_create(code=dept_code, college=college)
    DEPARTMENT_CACHE[key] = dept
    DEPARTMENT_ID_CACHE[key] = dept.id
    DEPARTMENT_BY_ID_CACHE[dept.id] = dept
    return dept


def ensure_curri(name: str, college: College, fuzzy_threshold: float = 1.0) -> Curriculum:
    """Return a Curriculum. Defaulting of the college curriculum if empyt name."""
    if not name:
        curriculum = Curriculum.get_dft(def_college=college)
        CURRICULUM_BY_ID_CACHE[curriculum.id] = curriculum
        return curriculum

    key = (name.lower(), college.id)
    cached = CURRICULUM_CACHE.get(key)
    if cached:
        CURRICULUM_ID_CACHE[name.lower()] = cached.id
        CURRICULUM_BY_ID_CACHE[cached.id] = cached
        return cached

    # get the Curriculum.field 'short_name' max_length
    SHORT_NAME_MAX = Curriculum._meta.get_field("short_name").max_length

    curriculum, _ = Curriculum.objects.get_or_create(
        short_name=name[:SHORT_NAME_MAX],
        college=college,
        defaults={"long_name": name},
        fuzzy_threshold=fuzzy_threshold,
    )
    CURRICULUM_CACHE[key] = curriculum
    CURRICULUM_ID_CACHE[name.lower()] = curriculum.id
    CURRICULUM_BY_ID_CACHE[curriculum.id] = curriculum

    return curriculum


def ensure_crs(
    department: Department,
    course_no: str,
    title: str | None = None,
    fuzzy_threshold: float = 1.0,
) -> Course:
    """Look-up or create a course updating the title is set."""
    course_no = _normalize_crs_no(course_no)

    key = (department.id, course_no)
    cached = COURSE_CACHE.get(key)
    if cached:
        COURSE_ID_CACHE[key] = cached.id
        COURSE_BY_ID_CACHE[cached.id] = cached
        return cached

    course, _created = Course.objects.get_or_create(
        department=department,
        number=course_no,
        defaults={"title": title},
        fuzzy_threshold=fuzzy_threshold,
    )

    # if _created:
    #     course.save()

    if title and course.title != title:
        course.title = title
        course.save(update_fields=["title"])

    COURSE_CACHE[key] = course
    COURSE_ID_CACHE[key] = course.id
    COURSE_BY_ID_CACHE[course.id] = course
    return course


def ensure_curri_crs(
    curriculum: Curriculum,
    course: Course,
    credit_code: int = 3,
    is_required: bool | None = None,
) -> CurriCourse:
    """Provide a CurriCourse cached if available."""
    key = (curriculum.id, course.id)
    cached = CURRICULUM_COURSE_CACHE.get(key)

    if cached:
        CURRICULUM_COURSE_ID_CACHE[key] = cached.id
        return cached

    # Ensure NOT NULL boolean defaults when imports omit the flag.
    is_required = bool(is_required)

    credit = CREDIT_HOUR_CACHE.get(credit_code)

    if credit is None:
        credit, _ = CreditHour.objects.get_or_create(code=credit_code)
        CREDIT_HOUR_CACHE[credit_code] = credit

    ccur, _ = CurriCourse.objects.get_or_create(
        curriculum=curriculum,
        course=course,
        defaults={"credit_hours": credit, "is_required": is_required},
    )
    CURRICULUM_COURSE_CACHE[key] = ccur
    CURRICULUM_COURSE_ID_CACHE[key] = ccur.id
    return ccur


def ensure_college_id(code_raw: str) -> int:
    """Return a college id for the given code."""
    code = normalize_college_code(code_raw)
    _prime_college_id_cache()
    cached = COLLEGE_ID_CACHE.get(code.lower())
    if cached:
        return cached
    college = ensure_college(code)
    return college.id


def ensure_dpt_id(dept_code_raw: str, college_id: int) -> int:
    """Return a department id for the given code and college id."""
    dept_code = normalize_dpt_code(dept_code_raw)
    key = (dept_code, college_id)
    _prime_dpt_id_cache()
    cached = DEPARTMENT_ID_CACHE.get(key)
    if cached:
        return cached
    college = _get_college_by_id(college_id)
    department = ensure_dpt(dept_code, college)
    return department.id


def ensure_crs_id(
    department_id: int,
    course_no_raw: str,
    title: str | None = None,
    fuzzy_threshold: float = 1.0,
) -> int:
    """Return a course id for the given department id and course number."""
    course_no = _normalize_crs_no(course_no_raw)
    key = (department_id, course_no)
    _prime_crs_id_cache()
    cached = COURSE_ID_CACHE.get(key)
    if cached:
        return cached
    department = _get_dpt_by_id(department_id)
    course = ensure_crs(
        department, course_no, title=title, fuzzy_threshold=fuzzy_threshold
    )
    return course.id


def ensure_curri_id(name_raw: str, college_id: int, fuzzy_threshold: float = 1.0) -> int:
    """Return a curriculum id for the given name and college id."""
    name = parse_str(name_raw)
    if not name:
        college = _get_college_by_id(college_id)
        curriculum = ensure_curri("", college, fuzzy_threshold=fuzzy_threshold)
        return curriculum.id
    key = name.lower()
    _prime_curri_id_cache()
    cached = CURRICULUM_ID_CACHE.get(key)
    if cached:
        return cached
    college = _get_college_by_id(college_id)
    curriculum = ensure_curri(name, college, fuzzy_threshold=fuzzy_threshold)
    return curriculum.id


def ensure_curri_crs_id(
    curriculum_id: int,
    course_id: int,
    credit_code: int = 3,
    is_required: bool | None = None,
) -> int:
    """Return a curriculum course id for the given curriculum/course ids."""
    key = (curriculum_id, course_id)
    _prime_curri_crs_id_cache()
    cached = CURRICULUM_COURSE_ID_CACHE.get(key)
    if cached:
        return cached
    curriculum = _get_curri_by_id(curriculum_id)
    course = _get_crs_by_id(course_id)
    curriculum_course = ensure_curri_crs(
        curriculum=curriculum,
        course=course,
        credit_code=credit_code,
        is_required=is_required,
    )
    return curriculum_course.id
