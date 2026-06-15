"""Source and matching helpers for TUCurricula prerequisite backfill."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from app.academics.models.course import Course
from app.shared.course_wrangling import (
    LEGACY_DEPT_ALIASES,
    course_key,
    normalize_token,
    split_course_code,
)
from app.shared.source_truth.fuzzy import title_similarity
from app.shared.source_truth.io import read_rows

CourseMapT: TypeAlias = dict[str, list[Course]]
SourceCourseMapT: TypeAlias = dict[str, "SourceCourseT"]

TITLE_MATCH_THRESHOLD = 0.94


@dataclass(frozen=True)
class SourceCourseT:
    """TUCurricula course identity and title for safe current-course matching."""

    key: str
    department: str
    number: str
    title: str
    source_files: str


@dataclass(frozen=True)
class SourcePrerequisiteT:
    """One unique source-level all-prerequisite edge."""

    target_key: str
    required_key: str
    source_files: str


def load_source_courses(import_dir: Path) -> SourceCourseMapT:
    """Load source course titles used to safely match legacy course variants."""
    courses: SourceCourseMapT = {}
    for row in read_rows(import_dir / "academic_course.tsv"):
        department = normalize_token(row.get("course_dept"))
        number = normalize_token(row.get("course_no"))
        if not department or not number:
            department, number = split_course_code(row.get("source_course_key"))
        key = course_key(department, number)
        if not key:
            continue
        courses.setdefault(
            key,
            SourceCourseT(
                key=key,
                department=department,
                number=number,
                title=(row.get("course_title") or "").strip(),
                source_files=(
                    row.get("source_files") or row.get("source_file") or ""
                ).strip(),
            ),
        )
    return courses


def load_source_prerequisites(import_dir: Path) -> list[SourcePrerequisiteT]:
    """Return unique source-level prereq_all edges."""
    by_pair: dict[tuple[str, str], SourcePrerequisiteT] = {}
    for row in read_rows(import_dir / "academic_curriculum_requirement.tsv"):
        if row.get("requirement_kind") != "prereq_all":
            continue
        target_key = course_key(row.get("course_dept"), row.get("course_no"))
        required_key = course_key(
            row.get("required_course_dept"), row.get("required_course_no")
        )
        if not target_key or not required_key:
            continue
        by_pair.setdefault(
            (target_key, required_key),
            SourcePrerequisiteT(
                target_key=target_key,
                required_key=required_key,
                source_files=(
                    row.get("source_file") or row.get("source_files") or ""
                ).strip(),
            ),
        )
    return list(by_pair.values())


def current_course_maps() -> tuple[CourseMapT, CourseMapT]:
    """Index current courses by comparison key and course number."""
    by_key: CourseMapT = {}
    by_number: CourseMapT = {}
    courses = Course.objects.select_related("department").order_by(
        "department__code", "number", "id"
    )
    for course in courses.iterator():
        key = course_key(course.department.code, course.number)
        number = normalize_token(course.number)
        by_key.setdefault(key, []).append(course)
        by_number.setdefault(number, []).append(course)
    return by_key, by_number


def matching_courses(
    source: SourceCourseT,
    current_by_key: CourseMapT,
    current_by_number: CourseMapT,
) -> list[Course]:
    """Return exact plus safe close-department current courses for a source key."""
    matches = {course.id: course for course in current_by_key.get(source.key, [])}
    if source.title:
        for course in current_by_number.get(source.number, []):
            if course.id in matches:
                continue
            if not close_department(source.department, course.department.code):
                continue
            if (
                title_similarity(source.title, course.title or "")
                >= TITLE_MATCH_THRESHOLD
            ):
                matches[course.id] = course
    return sorted(matches.values(), key=lambda course: int(course.id))


def representative_course(courses: list[Course], source_key: str) -> Course:
    """Choose one required-course row for display while statuses compare by key."""
    exact = [
        course
        for course in courses
        if course_key(course.department.code, course.number) == source_key
    ]
    return sorted(exact or courses, key=lambda course: int(course.id))[0]


def source_course(source_key: str, source_courses: SourceCourseMapT) -> SourceCourseT:
    """Return a source course record, falling back to identity-only data."""
    source = source_courses.get(source_key)
    if source is not None:
        return source
    department, number = split_course_code(source_key)
    return SourceCourseT(
        key=source_key,
        department=department,
        number=number,
        title="",
        source_files="",
    )


def close_department(source_dept: str, current_dept: str) -> bool:
    """Return True for approved or shape-close department-code variants."""
    source = normalize_token(source_dept)
    current = normalize_token(current_dept)
    if source == current:
        return True
    if LEGACY_DEPT_ALIASES.get(source) == current:
        return True
    if LEGACY_DEPT_ALIASES.get(current) == source:
        return True
    min_len = min(len(source), len(current))
    if min_len < 3:
        return False
    return source.startswith(current) or current.startswith(source)


__all__ = [
    "CourseMapT",
    "SourceCourseMapT",
    "SourceCourseT",
    "SourcePrerequisiteT",
    "close_department",
    "current_course_maps",
    "load_source_courses",
    "load_source_prerequisites",
    "matching_courses",
    "representative_course",
    "source_course",
]
