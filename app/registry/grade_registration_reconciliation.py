"""Reconcile historical registration rows from imported grade evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, TypeAlias

from app.registry.gpa import effective_transcript_grades
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.registry.models.status_types import RegistrationStatus
from app.timetable.models.section import Section

GradeRegistrationPairT: TypeAlias = tuple[int, int]


@dataclass
class GradeRegistrationSummary:
    """Counters for grade-backed registration reconstruction."""

    processed: int = 0
    existing: int = 0
    created: int = 0
    would_create: int = 0

    def add(self, other: "GradeRegistrationSummary") -> None:
        """Accumulate counters from another summary."""
        self.processed += other.processed
        self.existing += other.existing
        self.created += other.created
        self.would_create += other.would_create


@dataclass(frozen=True)
class StudentCreditGap:
    """Student whose registered credits are below passing-grade credits."""

    student_id: int
    registered_credits: int
    passing_credits: int


def ensure_grade_registration_pairs(
    pairs: Iterable[GradeRegistrationPairT],
    *,
    batch_size: int = 5000,
    dry_run: bool = False,
) -> GradeRegistrationSummary:
    """Ensure cleared registrations exist for grade-backed student/section pairs."""
    unique_pairs = {
        (int(student_id), int(section_id))
        for student_id, section_id in pairs
        if student_id and section_id
    }
    summary = GradeRegistrationSummary(processed=len(unique_pairs))
    if not unique_pairs:
        return summary

    RegistrationStatus._populate_attributes_and_db()
    section_course_ids, section_credits = _section_course_credit_maps(unique_pairs)
    existing_pairs = _existing_registration_pairs(
        unique_pairs,
        section_course_ids,
        section_credits,
    )
    missing_pairs = _collapse_missing_pairs_by_course(
        unique_pairs - existing_pairs,
        section_course_ids,
        section_credits,
    )
    summary.existing = len(existing_pairs & unique_pairs)
    if dry_run:
        summary.would_create = len(missing_pairs)
        return summary
    registrations = [
        Registration(
            student_id=student_id,
            section_id=section_id,
            status_id="cleared",
        )
        for student_id, section_id in missing_pairs
    ]
    Registration.objects.bulk_create(
        registrations,
        ignore_conflicts=True,
        batch_size=batch_size,
    )
    summary.created = len(registrations)
    return summary


def ensure_grade_registrations_for_grades(
    grades: Iterable[Grade],
    *,
    batch_size: int = 5000,
    dry_run: bool = False,
) -> GradeRegistrationSummary:
    """Ensure registrations exist for the sections referenced by grades."""
    return ensure_grade_registration_pairs(
        ((grade.student_id, grade.section_id) for grade in grades),
        batch_size=batch_size,
        dry_run=dry_run,
    )


def student_credit_gaps(
    *,
    student_id: int | None = None,
    limit: int | None = None,
) -> list[StudentCreditGap]:
    """Return students where registered credits are below passing-grade credits."""
    registered = _registered_credit_totals(student_id=student_id)
    gaps: list[StudentCreditGap] = []
    for grade_student_id, passing_credits in _passing_credit_totals(student_id):
        registered_credits = registered.get(grade_student_id, 0)
        if registered_credits >= passing_credits:
            continue
        gaps.append(
            StudentCreditGap(
                student_id=grade_student_id,
                registered_credits=registered_credits,
                passing_credits=passing_credits,
            )
        )
        if limit is not None and len(gaps) >= limit:
            break
    return gaps


def _existing_registration_pairs(
    pairs: set[GradeRegistrationPairT],
    section_course_ids: dict[int, int],
    section_credits: dict[int, int],
) -> set[GradeRegistrationPairT]:
    """Return candidate pairs already covered by a same-course registration."""
    student_ids = {student_id for student_id, _section_id in pairs}
    course_ids = set(section_course_ids.values())
    registered_credits = _registered_course_credit_totals(
        student_ids=student_ids,
        course_ids=course_ids,
    )
    return {
        (student_id, section_id)
        for student_id, section_id in pairs
        if registered_credits.get(
            (student_id, section_course_ids.get(section_id, 0)),
            0,
        )
        >= section_credits.get(section_id, 0)
    }


def _section_course_credit_maps(
    pairs: set[GradeRegistrationPairT],
) -> tuple[dict[int, int], dict[int, int]]:
    """Return section maps for base course ids and section credit hours."""
    section_ids = {section_id for _student_id, section_id in pairs}
    course_ids: dict[int, int] = {}
    credits: dict[int, int] = {}
    for section_id, course_id, credit_hours in Section.objects.filter(
        id__in=section_ids
    ).values_list(
        "id",
        "curriculum_course__course_id",
        "curriculum_course__credit_hours_id",
    ):
        course_ids[int(section_id)] = int(course_id)
        credits[int(section_id)] = int(credit_hours or 0)
    return course_ids, credits


def _registered_course_credit_totals(
    *,
    student_ids: set[int],
    course_ids: set[int],
) -> dict[tuple[int, int], int]:
    """Return registered credits keyed by student and base course."""
    totals: dict[tuple[int, int], int] = {}
    registrations = Registration.objects.filter(
        student_id__in=student_ids,
        section__curriculum_course__course_id__in=course_ids,
    ).values_list(
        "student_id",
        "section__curriculum_course__course_id",
        "section__curriculum_course__credit_hours_id",
    )
    for student_id, course_id, credit_hours in registrations:
        key = (int(student_id), int(course_id))
        totals[key] = totals.get(key, 0) + int(credit_hours or 0)
    return totals


def _collapse_missing_pairs_by_course(
    pairs: set[GradeRegistrationPairT],
    section_course_ids: dict[int, int],
    section_credits: dict[int, int],
) -> list[GradeRegistrationPairT]:
    """Choose the highest-credit registration candidate per student/course gap."""
    selected: dict[tuple[int, int], GradeRegistrationPairT] = {}
    for student_id, section_id in sorted(pairs):
        course_id = section_course_ids.get(section_id)
        if course_id is None:
            continue
        course_key = (student_id, course_id)
        current = selected.get(course_key)
        if current is None or section_credits.get(section_id, 0) > section_credits.get(
            current[1],
            0,
        ):
            selected[course_key] = (student_id, section_id)
    return list(selected.values())


def _registered_credit_totals(*, student_id: int | None = None) -> dict[int, int]:
    """Return non-canceled registration credits keyed by student id."""
    qs = (
        Registration.objects.exclude(status_id="canceled")
        .select_related("section__curriculum_course__credit_hours")
        .order_by("student_id")
    )
    if student_id is not None:
        qs = qs.filter(student_id=student_id)
    totals: dict[int, int] = {}
    for registration in qs.iterator(chunk_size=5000):
        current_student_id = int(registration.student_id)
        totals[current_student_id] = totals.get(current_student_id, 0) + int(
            registration.section.curriculum_course.credit_hours_id or 0
        )
    return totals


def _passing_credit_totals(student_id: int | None = None) -> list[tuple[int, int]]:
    """Return transcript passing credits keyed by student id."""
    qs = (
        Grade.objects.filter(is_effective=True, value__number__gte=1)
        .select_related(
            "value",
            "section__semester",
            "section__curriculum_course__credit_hours",
            "section__curriculum_course__course",
            "section__curriculum_course__course__department",
        )
        .order_by("student_id", "section__semester__start_date", "section_id", "id")
    )
    if student_id is not None:
        qs = qs.filter(student_id=student_id)

    totals: list[tuple[int, int]] = []
    current_student_id: int | None = None
    student_grades: list[Grade] = []
    for grade in qs.iterator(chunk_size=5000):
        if current_student_id is None:
            current_student_id = int(grade.student_id)
        if grade.student_id != current_student_id:
            totals.append((current_student_id, _passing_credits(student_grades)))
            current_student_id = int(grade.student_id)
            student_grades = []
        student_grades.append(grade)
    if current_student_id is not None:
        totals.append((current_student_id, _passing_credits(student_grades)))
    return totals


def _passing_credits(grades: Iterable[Grade]) -> int:
    """Return passing credits after transcript alias collapse."""
    return sum(
        int(grade.section.curriculum_course.credit_hours_id or 0)
        for grade in effective_transcript_grades(grades)
    )


__all__ = [
    "GradeRegistrationPairT",
    "GradeRegistrationSummary",
    "StudentCreditGap",
    "ensure_grade_registration_pairs",
    "ensure_grade_registrations_for_grades",
    "student_credit_gaps",
]
