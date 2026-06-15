"""Build student-facing course information blocks."""

from __future__ import annotations

from typing import TypeAlias, TypedDict

from django.db.models import Q

from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.course import Course
from app.academics.models.prerequisite import Prerequisite
from app.academics.models.requirement_group import (
    CurriCrsReqMember,
    ReqKind,
)
from app.people.models.student import Student
from app.registry.models.registration import Registration
from app.shared.course_wrangling import course_key

CourseKeySetT: TypeAlias = set[str]
SeenKeySetT: TypeAlias = set[tuple[str, str]]


class CourseRequirementT(TypedDict):
    """Student-facing prerequisite/corequisite row."""

    code: str
    title: str
    status_label: str
    met: bool
    note: str


class CourseUnlockT(TypedDict):
    """Course unlocked after completing the current course."""

    code: str
    title: str
    note: str


class StudentCourseInfoT(TypedDict):
    """Shared course detail payload for student views."""

    code: str
    title: str
    credits: int
    description: str
    curriculum_label: str
    prerequisites: list[CourseRequirementT]
    corequisites: list[CourseRequirementT]
    unlocks: list[CourseUnlockT]


def _course_code(course: Course) -> str:
    """Return the preferred student-facing course code."""
    return course.short_code or course.code or ""


def _course_identity_key(course: Course) -> str:
    """Return the normalized course identity used for duplicate-safe statuses."""
    return course_key(course.department.code, course.number)


def _append_requirement(
    rows: list[CourseRequirementT],
    *,
    course: Course,
    seen: SeenKeySetT,
    kind: str,
    met: bool,
    status_label: str,
    note: str,
) -> None:
    """Append one deduplicated requirement row."""
    key = (kind, _course_identity_key(course))
    if key in seen:
        return
    seen.add(key)
    rows.append(
        {
            "code": _course_code(course),
            "title": course.title or "",
            "status_label": status_label,
            "met": met,
            "note": note,
        }
    )


def _append_unlock(
    rows: list[CourseUnlockT],
    *,
    course: Course,
    seen: CourseKeySetT,
    note: str,
) -> None:
    """Append one deduplicated course unlocked by the current course."""
    key = _course_identity_key(course)
    if key in seen:
        return
    seen.add(key)
    rows.append(
        {
            "code": _course_code(course),
            "title": course.title or "",
            "note": note,
        }
    )


def _active_course_keys(student: Student) -> CourseKeySetT:
    """Return courses in active student registrations."""
    return {
        course_key(dept, number)
        for dept, number in (
            Registration.objects.filter(
                student=student,
                status_id__in={"pending", "approved", "cleared"},
            ).values_list(
                "section__curriculum_course__course__department__code",
                "section__curriculum_course__course__number",
            )
        )
    }


def _passed_course_keys(student: Student) -> CourseKeySetT:
    """Return completed course identities, stable across duplicate Course rows."""
    return {
        course_key(dept, number)
        for dept, number in student.passed_crss().values_list(
            "department__code",
            "number",
        )
    }


def _prereq_status(course: Course, passed_course_keys: CourseKeySetT) -> tuple[bool, str]:
    """Return completion status for a prerequisite course."""
    if _course_identity_key(course) in passed_course_keys:
        return True, "Completed"
    return False, "Not completed"


def _coreq_status(
    course: Course,
    *,
    active_course_keys: CourseKeySetT,
    passed_course_keys: CourseKeySetT,
) -> tuple[bool, str]:
    """Return current status for a corequisite course."""
    key = _course_identity_key(course)
    if key in active_course_keys:
        return True, "Selected"
    if key in passed_course_keys:
        return True, "Completed"
    return False, "Take together"


def build_student_course_info(
    *,
    student: Student,
    curriculum_course: CurriCrs,
) -> StudentCourseInfoT:
    """Build one shared course-information payload for student pages."""
    course = curriculum_course.course
    curriculum = curriculum_course.curriculum
    passed_course_keys = _passed_course_keys(student)
    active_course_keys = _active_course_keys(student)
    prerequisites: list[CourseRequirementT] = []
    corequisites: list[CourseRequirementT] = []
    seen_requirements: SeenKeySetT = set()

    legacy_prereqs = (
        Prerequisite.objects.filter(
            Q(curriculum=curriculum) | Q(curriculum__isnull=True),
            course=course,
        )
        .select_related("prerequisite_course")
        .order_by("prerequisite_course__short_code", "prerequisite_course__code")
    )
    for prereq in legacy_prereqs:
        met, status_label = _prereq_status(
            prereq.prerequisite_course,
            passed_course_keys,
        )
        _append_requirement(
            prerequisites,
            course=prereq.prerequisite_course,
            seen=seen_requirements,
            kind="prereq",
            met=met,
            status_label=status_label,
            note="Required before registration",
        )

    for group in curriculum_course.requirement_groups.all().prefetch_related(
        "members__required_course"
    ):
        if group.kind not in {
            ReqKind.PREREQ_ALL,
            ReqKind.PREREQ_ANY,
            ReqKind.COREQ_ALL,
        }:
            continue
        target_rows = corequisites if group.kind == ReqKind.COREQ_ALL else prerequisites
        kind = "coreq" if group.kind == ReqKind.COREQ_ALL else "prereq"
        for member in group.members.all():
            required_course = member.required_course
            if group.kind == ReqKind.COREQ_ALL:
                met, status_label = _coreq_status(
                    required_course,
                    active_course_keys=active_course_keys,
                    passed_course_keys=passed_course_keys,
                )
                note = group.label or "Must be taken together"
            else:
                met, status_label = _prereq_status(
                    required_course,
                    passed_course_keys,
                )
                note = group.label or "Required before registration"
            _append_requirement(
                target_rows,
                course=required_course,
                seen=seen_requirements,
                kind=kind,
                met=met,
                status_label=status_label,
                note=note,
            )

    unlocks: list[CourseUnlockT] = []
    seen_unlocks: CourseKeySetT = set()
    dependent_prereqs = (
        Prerequisite.objects.filter(
            Q(curriculum=curriculum) | Q(curriculum__isnull=True),
            prerequisite_course=course,
            course__in_curriculum_courses__curriculum=curriculum,
        )
        .select_related("course")
        .order_by("course__short_code", "course__code")
    )
    for prereq in dependent_prereqs:
        _append_unlock(
            unlocks,
            course=prereq.course,
            seen=seen_unlocks,
            note="Prerequisite path",
        )

    dependent_members = (
        CurriCrsReqMember.objects.filter(
            required_course=course,
            group__curriculum_course__curriculum=curriculum,
            group__kind__in={ReqKind.PREREQ_ALL, ReqKind.PREREQ_ANY},
        )
        .select_related("group__curriculum_course__course")
        .order_by(
            "group__curriculum_course__course__short_code",
            "group__curriculum_course__course__code",
        )
    )
    for member in dependent_members:
        _append_unlock(
            unlocks,
            course=member.group.curriculum_course.course,
            seen=seen_unlocks,
            note=member.group.label or "Requirement path",
        )

    return {
        "code": _course_code(course),
        "title": course.title or "",
        "credits": int(curriculum_course.credit_hours.code),
        "description": course.description or "No description available.",
        "curriculum_label": str(curriculum),
        "prerequisites": prerequisites,
        "corequisites": corequisites,
        "unlocks": unlocks,
    }


__all__ = [
    "CourseRequirementT",
    "CourseUnlockT",
    "StudentCourseInfoT",
    "build_student_course_info",
]
