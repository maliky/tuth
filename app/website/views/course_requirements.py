"""Typed helpers to evaluate curriculum-course registration requirements."""

from __future__ import annotations

from typing import Iterable, TypeAlias, TypedDict

from app.academics.models.curriculum_course import CurriCourse
from app.academics.models.requirement_group import (
    CurriCourseReqGp,
    ReqKind,
)
from app.people.models.student import Student

CourseIdsT: TypeAlias = set[int]
CourseLabelPairT: TypeAlias = tuple[int, str]
ReqFailureListT: TypeAlias = list["ReqFailureT"]


class ReqContextT(TypedDict):
    """Cached student requirement facts shared across evaluations."""

    passed_course_ids: CourseIdsT
    validated_credits: int


class ReqFailureT(TypedDict, total=False):
    """Machine-readable detail for one failed requirement rule."""

    code: str
    group_id: int | None
    group_kind: str
    group_label: str
    missing_course_ids: list[int]
    missing_course_labels: list[str]
    required_credits: int
    validated_credits: int


class ReqCheckResultT(TypedDict):
    """Structured requirement-evaluation result."""

    ok: bool
    failures: ReqFailureListT


def build_req_context(student: Student) -> ReqContextT:
    """Build shared student facts used by all course requirement checks."""
    passed_course_ids = set(student.passed_crss().values_list("id", flat=True))
    return {
        "passed_course_ids": passed_course_ids,
        "validated_credits": int(student.completed_credits or 0),
    }


def _gp_member_pairs(
    group: CurriCourseReqGp,
) -> list[CourseLabelPairT]:
    """Return `(course_id, display_label)` pairs for one requirement group."""
    return [
        (
            member.required_course_id,
            member.required_course.short_code or member.required_course.code,
        )
        for member in group.members.all()
    ]


def eval_curri_crs_reqs(
    *,
    student: Student,
    curriculum_course: CurriCourse,
    selected_course_ids: Iterable[int],
    context: ReqContextT | None = None,
) -> ReqCheckResultT:
    """Evaluate credit/prerequisite/corequisite rules for one curriculum course."""
    eval_context = context or build_req_context(student)
    selected_ids = set(selected_course_ids)
    passed_ids = eval_context["passed_course_ids"]
    validated_credits = int(eval_context["validated_credits"])

    failures: ReqFailureListT = []

    min_credits = int(curriculum_course.min_validated_credits or 0)
    if validated_credits < min_credits:
        failures.append(
            {
                "code": "missing_credits",
                "group_id": None,
                "required_credits": min_credits,
                "validated_credits": validated_credits,
            }
        )

    groups = curriculum_course.requirement_groups.all().prefetch_related(
        "members__required_course"
    )
    for group in groups:
        member_pairs = _gp_member_pairs(group)
        if not member_pairs:
            continue
        group_common: ReqFailureT = {
            "group_id": group.id,
            "group_kind": group.kind,
            "group_label": group.label,
        }

        if group.kind == ReqKind.PREREQ_ALL:
            missing_pairs = [
                (course_id, label)
                for course_id, label in member_pairs
                if course_id not in passed_ids
            ]
            if missing_pairs:
                failures.append(
                    {
                        **group_common,
                        "code": "missing_prereq_all",
                        "missing_course_ids": [
                            course_id for course_id, _ in missing_pairs
                        ],
                        "missing_course_labels": [label for _, label in missing_pairs],
                    }
                )
            continue

        if group.kind == ReqKind.PREREQ_ANY:
            has_any_match = any(course_id in passed_ids for course_id, _ in member_pairs)
            if not has_any_match:
                failures.append(
                    {
                        **group_common,
                        "code": "unsatisfied_prereq_any",
                        "missing_course_ids": [
                            course_id for course_id, _ in member_pairs
                        ],
                        "missing_course_labels": [label for _, label in member_pairs],
                    }
                )
            continue

        if group.kind == ReqKind.COREQ_ALL:
            missing_pairs = [
                (course_id, label)
                for course_id, label in member_pairs
                if course_id not in selected_ids
            ]
            if missing_pairs:
                failures.append(
                    {
                        **group_common,
                        "code": "incomplete_coreq_all",
                        "missing_course_ids": [
                            course_id for course_id, _ in missing_pairs
                        ],
                        "missing_course_labels": [label for _, label in missing_pairs],
                    }
                )

    return {"ok": not failures, "failures": failures}


def req_failure_msgs(
    failures: ReqFailureListT,
) -> list[str]:
    """Convert machine-readable failures into user-facing message lines."""
    messages: list[str] = []
    for failure in failures:
        code = failure.get("code", "")
        if code == "missing_credits":
            required = int(failure.get("required_credits", 0))
            current = int(failure.get("validated_credits", 0))
            messages.append(
                f"Requires at least {required} validated credits (currently {current})."
            )
            continue

        labels = list(failure.get("missing_course_labels", []))
        if code == "missing_prereq_all":
            messages.append(f"Complete {', '.join(labels)} first.")
            continue
        if code == "unsatisfied_prereq_any":
            messages.append(f"Complete at least one of: {', '.join(labels)}.")
            continue
        if code == "incomplete_coreq_all":
            messages.append(f"Must be selected together with: {', '.join(labels)}.")

    return messages
