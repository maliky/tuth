"""Shared helpers for academics merge workflows."""

from __future__ import annotations

from typing import Literal, TypeAlias, no_type_check

from django.db import transaction
from django.db.models import Count

from app.academics.models.concentration import MajorCurriCourse, MinorCurriCourse
from app.academics.models.course import Course
from app.academics.models.curriculum_course import CurriCourse
from app.academics.models.department import Department
from app.people.models import RoleAssignment, Staff

CourseMergeSummaryT: TypeAlias = dict[str, int]
ConflictChoiceT = Literal["keep_target", "keep_source", "merge", "skip"]
ConflictChoiceByCourseIdT: TypeAlias = dict[int, ConflictChoiceT]
ConflictCurriCoursePairT: TypeAlias = tuple[CurriCourse, CurriCourse]
SectionMergeResultT: TypeAlias = dict[str, int]
StdCurriRecordMergeSummaryT: TypeAlias = dict[str, int]
CourseIdentityT: TypeAlias = tuple[int, str]

MERGE_CHOICE_KEEP_TARGET: ConflictChoiceT = "keep_target"
MERGE_CHOICE_KEEP_SOURCE: ConflictChoiceT = "keep_source"
MERGE_CHOICE_MERGE: ConflictChoiceT = "merge"
MERGE_CHOICE_SKIP: ConflictChoiceT = "skip"


def _build_course_identity(
    department_id: int | None, course_number: str | None
) -> CourseIdentityT | None:
    """Return the canonical identity key used for cross-curriculum reconciliation."""
    if not department_id:
        return None
    if course_number is None:
        return None
    normalized_number = str(course_number).strip()
    if not normalized_number:
        return None
    return (int(department_id), normalized_number)


def _curriculum_course_identity(curriculum_course: CurriCourse) -> CourseIdentityT | None:
    """Return a curriculum-course identity as (department_id, course_number)."""
    course = getattr(curriculum_course, "course", None)
    if course is None:
        return None
    return _build_course_identity(course.department_id, course.number)


def _index_curriculum_courses_by_identity(
    curriculum_courses: list[CurriCourse],
) -> dict[CourseIdentityT, CurriCourse]:
    """Index rows by identity while keeping the lowest-id row as canonical."""
    identity_index: dict[CourseIdentityT, CurriCourse] = {}
    for curriculum_course in sorted(curriculum_courses, key=lambda row: int(row.id)):
        identity = _curriculum_course_identity(curriculum_course)
        if identity is None:
            continue
        if identity in identity_index:
            continue
        identity_index[identity] = curriculum_course
    return identity_index


def _identity_by_curriculum_course_id(
    curriculum_courses: list[CurriCourse],
) -> dict[int, CourseIdentityT]:
    """Build an id->identity lookup for already-fetched curriculum course rows."""
    identity_by_curriculum_course_id: dict[int, CourseIdentityT] = {}
    for curriculum_course in curriculum_courses:
        identity = _curriculum_course_identity(curriculum_course)
        if identity is None:
            continue
        identity_by_curriculum_course_id[curriculum_course.id] = identity
    return identity_by_curriculum_course_id


def empty_student_curriculum_record_summary() -> StdCurriRecordMergeSummaryT:
    """Return the default counters for student-scoped curriculum reconciliation."""
    return {
        "grades_moved": 0,
        "grades_deduped": 0,
        "grade_conflicts": 0,
        "grades_unresolved": 0,
        "registrations_moved": 0,
        "registrations_deduped": 0,
        "registrations_unresolved": 0,
    }


def _merge_curriculum_course_links(target: CurriCourse, source: CurriCourse) -> None:
    """Move concentration links from a source curriculum course to the target."""
    for major_link in MajorCurriCourse.objects.filter(curriculum_course=source):
        if MajorCurriCourse.objects.filter(
            major_id=major_link.major_id, curriculum_course=target
        ).exists():
            continue
        major_link.curriculum_course = target
        major_link.save(update_fields=["curriculum_course"])
    for minor_link in MinorCurriCourse.objects.filter(curriculum_course=source):
        if MinorCurriCourse.objects.filter(
            minor_id=minor_link.minor_id, curriculum_course=target
        ).exists():
            continue
        minor_link.curriculum_course = target
        minor_link.save(update_fields=["curriculum_course"])


@transaction.atomic
def merge_departments(target: Department, sources):
    """Merge departments by reassigning dependent records to the target."""
    summary = {
        "merged": 0,
        "courses_moved": 0,
        "course_codes_rebuilt": 0,
        "staff_moved": 0,
        "roles_moved": 0,
    }
    for src in sources:
        if src.pk == target.pk:
            continue
        courses = list(Course.objects.filter(department=src))
        for course in courses:
            course.department = target
            course.code = ""
            course.short_code = ""
            course.save(update_fields=["department", "code", "short_code"])
        summary["courses_moved"] += len(courses)
        summary["course_codes_rebuilt"] += len(courses)
        summary["staff_moved"] += Staff.objects.filter(department=src).update(
            department=target
        )
        summary["roles_moved"] += RoleAssignment.objects.filter(department=src).update(
            department=target
        )
        Department.objects.filter(pk=src.pk).delete()
        summary["merged"] += 1
    return summary


# Avoid mypy internal error on the annotate chain for collision summaries.
@no_type_check
def _department_merge_collision_summary(target: Department, sources) -> dict[str, int]:
    """Summarize potential department merge collisions."""
    source_ids = [dept.pk for dept in sources if dept.pk]
    if not target.pk or not source_ids:
        return {
            "course_number_collisions": 0,
            "source_course_count": 0,
            "source_staff_count": 0,
            "source_role_count": 0,
        }
    dept_ids = [target.pk] + source_ids
    collisions = (
        Course.objects.filter(department_id__in=dept_ids)
        .values("number")
        .annotate(course_count=Count("id"))
        .filter(course_count__gt=1)
    )
    return {
        "course_number_collisions": collisions.count(),
        "source_course_count": Course.objects.filter(
            department_id__in=source_ids
        ).count(),
        "source_staff_count": Staff.objects.filter(department_id__in=source_ids).count(),
        "source_role_count": RoleAssignment.objects.filter(
            department_id__in=source_ids
        ).count(),
    }
