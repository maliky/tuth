"""Shared fast lookup helpers for academic imports."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from app.shared.models import CreditHour
from app.academics.choices import COLLEGE_CODE, COLLEGE_LONG_NAME
from app.academics.models.college import College
from app.academics.models.course import Course, CurriculumCourse
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department

COLLEGE_CACHE: Dict[str, College] = {}
DEPARTMENT_CACHE: Dict[Tuple[str, int], Department] = {}
COURSE_CACHE: Dict[Tuple[int, str], Course] = {}
CURRICULUM_CACHE: Dict[Tuple[str, Optional[int]], Curriculum] = {}
CURRICULUM_COURSE_CACHE: Dict[Tuple[int, int], CurriculumCourse] = {}
CREDIT_HOUR_CACHE: Dict[int, CreditHour] = {}


def ensure_college(code_raw: str) -> College:
    """Return the college attached to code_raw if possible cached."""
    code = COLLEGE_CODE.get((code_raw.lower() or ""), "DEFT")
    cached = COLLEGE_CACHE.get(code)
    if cached:
        return cached
    college, _ = College.objects.get_or_create(
        code=code,
        defaults={"long_name": COLLEGE_LONG_NAME.get(code.lower(), code)},
    )
    COLLEGE_CACHE[code] = college
    return college


def ensure_department(dept_code_raw: str, college: College) -> Department:
    dept_code = (dept_code_raw or "DEFT").strip().upper()
    key = (dept_code, college.id)
    cached = DEPARTMENT_CACHE.get(key)
    if cached:
        return cached
    dept, _ = Department.objects.get_or_create(code=dept_code, college=college)
    DEPARTMENT_CACHE[key] = dept
    return dept


def ensure_curriculum(
    name: str, college: College, fuzzy_threshold: float = 1.0
) -> Curriculum:
    """Return a Curriculum attached"""
    if not name:
        return Curriculum.get_default()
    
    key = (name.lower(), college.id if college else None)
    cached = CURRICULUM_CACHE.get(key)
    if cached:
        return cached

    SHORT_NAME_MAX = Curriculum._meta.get_field("short_name").max_length
    
    curriculum, _ = Curriculum.objects.get_or_create(
        short_name=name[:SHORT_NAME_MAX],
        college=college,
        defaults={"long_name": name},
        fuzzy_threshold=fuzzy_threshold,
    )
    CURRICULUM_CACHE[key] = curriculum
    return curriculum


def ensure_course(
    department: Department,
    course_no_raw: str,
    title: str | None = None,
    fuzzy_threshold: float = 1.0,
) -> Course:
    course_no = (course_no_raw or "").strip()
    if course_no.endswith(".0"):
        course_no = course_no[:-2]
    key = (department.id, course_no)
    cached = COURSE_CACHE.get(key)
    if cached:
        return cached
    course, _ = Course.objects.get_or_create(
        department=department,
        number=course_no,
        defaults={"title": title},
        fuzzy_threshold=fuzzy_threshold,
    )
    if title and course.title != title:
        course.title = title
        course.save(update_fields=["title"])
    COURSE_CACHE[key] = course
    return course


def ensure_curriculum_course(
    curriculum: Curriculum,
    course: Course,
    credit_code: int = 3,
    is_required: bool | None = None,
) -> CurriculumCourse:
    key = (curriculum.id, course.id)
    cached = CURRICULUM_COURSE_CACHE.get(key)
    if cached:
        return cached
    credit = CREDIT_HOUR_CACHE.get(credit_code)
    if credit is None:
        credit, _ = CreditHour.objects.get_or_create(
            code=credit_code, defaults={"label": str(credit_code)}
        )
        CREDIT_HOUR_CACHE[credit_code] = credit
    cc, _ = CurriculumCourse.objects.get_or_create(
        curriculum=curriculum,
        course=course,
        defaults={
            "credit_hours": credit,
            "is_required": bool(is_required) if is_required is not None else False,
        },
    )
    CURRICULUM_COURSE_CACHE[key] = cc
    return cc
