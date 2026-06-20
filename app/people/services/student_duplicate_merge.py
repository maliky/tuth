"""Safe merge mechanics for duplicate student records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from django.db import transaction

from app.finance.models.invoice import CrsInvoice, StdSemesterInvoice
from app.finance.models.invoice_snapshot import InvoiceSnapshot
from app.finance.models.scholarship import Scholarship, ScholarshipTermSnapshot
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import StdCurriEnroll
from app.people.services.merge_people import merge_people
from app.people.services.student_duplicates import CountMapT, student_operational_counts
from app.registry.models.document import DocStd
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.registry.models.transcript import TranscriptRequest

SectionIdsT: TypeAlias = set[int]
InvoiceKeysT: TypeAlias = set[tuple[int, int]]


@dataclass(frozen=True)
class StudentMergeConflictT:
    """One reason a student merge cannot be applied safely."""

    model_name: str
    key: str


@dataclass(frozen=True)
class StudentMergeResultT:
    """Dry-run or applied result for one source -> target student merge."""

    target_id: int
    source_id: int
    applied: bool
    counts: CountMapT
    conflicts: list[StudentMergeConflictT]


def safe_merge_student(
    target: Student,
    source: Student,
    *,
    apply: bool = False,
) -> StudentMergeResultT:
    """Merge source into target after checking row-level uniqueness collisions."""
    conflicts = _merge_conflicts(target, source)
    counts = student_operational_counts(source)
    if conflicts or not apply:
        return StudentMergeResultT(
            target_id=target.pk,
            source_id=source.pk,
            applied=False,
            counts=counts,
            conflicts=conflicts,
        )

    with transaction.atomic():
        locked_target = Student.objects.select_for_update().get(pk=target.pk)
        locked_source = Student.objects.select_for_update().get(pk=source.pk)
        conflicts = _merge_conflicts(locked_target, locked_source)
        if conflicts:
            return StudentMergeResultT(
                target_id=locked_target.pk,
                source_id=locked_source.pk,
                applied=False,
                counts=counts,
                conflicts=conflicts,
            )
        _apply_student_relation_moves(locked_target, locked_source, counts)
        merge_people(locked_target, locked_source)
    return StudentMergeResultT(
        target_id=target.pk,
        source_id=source.pk,
        applied=True,
        counts=counts,
        conflicts=[],
    )


def _section_ids(model, student: Student) -> SectionIdsT:
    """Return section ids attached to a student through a section-based model."""
    return set(model.objects.filter(student=student).values_list("section_id", flat=True))


def _course_invoice_keys(student: Student) -> InvoiceKeysT:
    """Return course-invoice uniqueness keys for one student."""
    return set(
        CrsInvoice.objects.filter(student=student).values_list(
            "curriculum_course_id",
            "semester_id",
        )
    )


def _semester_ids(model, student: Student) -> SectionIdsT:
    """Return semester ids for a student-linked model."""
    return set(
        model.objects.filter(student=student).values_list("semester_id", flat=True)
    )


def _merge_conflicts(target: Student, source: Student) -> list[StudentMergeConflictT]:
    """Return collisions that would violate unique constraints after reassignment."""
    conflicts: list[StudentMergeConflictT] = []
    for section_id in sorted(
        _section_ids(Registration, target) & _section_ids(Registration, source)
    ):
        conflicts.append(StudentMergeConflictT("Registration", f"section={section_id}"))
    for section_id in sorted(_section_ids(Grade, target) & _section_ids(Grade, source)):
        conflicts.append(StudentMergeConflictT("Grade", f"section={section_id}"))
    for course_id, semester_id in sorted(
        _course_invoice_keys(target) & _course_invoice_keys(source)
    ):
        conflicts.append(
            StudentMergeConflictT(
                "CrsInvoice",
                f"curriculum_course={course_id},semester={semester_id}",
            )
        )
    for semester_id in sorted(
        _semester_ids(StdSemesterInvoice, target)
        & _semester_ids(StdSemesterInvoice, source)
    ):
        conflicts.append(
            StudentMergeConflictT("StdSemesterInvoice", f"semester={semester_id}")
        )
    for semester_id in sorted(
        _semester_ids(ScholarshipTermSnapshot, target)
        & _semester_ids(ScholarshipTermSnapshot, source)
    ):
        conflicts.append(
            StudentMergeConflictT("ScholarshipTermSnapshot", f"semester={semester_id}")
        )
    return conflicts


def _apply_student_relation_moves(
    target: Student,
    source: Student,
    counts: CountMapT,
) -> None:
    """Reassign source operational rows before deleting the duplicate profile."""
    _move_curriculum_enrollments(target, source, counts)
    course_ids = set(
        Grade.objects.filter(student=source).values_list(
            "section__curriculum_course__course_id",
            flat=True,
        )
    )
    counts["registrations"] = Registration.objects.filter(student=source).update(
        student=target
    )
    counts["grades"] = Grade.objects.filter(student=source).update(student=target)
    parent_ids = set(
        StdSemesterInvoice.objects.filter(student=source).values_list("id", flat=True)
    )
    counts["semester_invoices"] = StdSemesterInvoice.objects.filter(
        student=source
    ).update(student=target)
    counts["course_invoices"] = CrsInvoice.objects.filter(student=source).update(
        student=target
    )
    counts["scholarships"] = Scholarship.objects.filter(student=source).update(
        student=target
    )
    counts["scholarship_snapshots"] = ScholarshipTermSnapshot.objects.filter(
        student=source
    ).update(student=target)
    counts["invoice_snapshots"] = InvoiceSnapshot.objects.filter(student=source).update(
        student=target
    )
    counts["transcript_requests"] = TranscriptRequest.objects.filter(
        student=source
    ).update(student=target)
    counts["documents"] = DocStd.objects.filter(person=source).update(person=target)
    for parent_invoice in StdSemesterInvoice.objects.filter(pk__in=parent_ids):
        parent_invoice.refresh_totals_from_sources(save_model=True)
    for course_id in course_ids:
        Grade.recompute_effective_for_student_course(
            student_id=target.pk,
            course_id=course_id,
        )


def _move_curriculum_enrollments(
    target: Student,
    source: Student,
    counts: CountMapT,
) -> None:
    """Move non-duplicate curriculum enrollments and drop exact duplicates."""
    target_curriculum_ids = set(
        StdCurriEnroll.objects.filter(student=target).values_list(
            "curriculum_id",
            flat=True,
        )
    )
    target_has_primary = StdCurriEnroll.objects.filter(
        student=target,
        is_primary=True,
    ).exists()
    moved = 0
    removed = 0
    for enroll in StdCurriEnroll.objects.filter(student=source):
        if enroll.curriculum_id in target_curriculum_ids:
            enroll.delete()
            removed += 1
            continue
        enroll.student = target
        if enroll.is_primary and target_has_primary:
            enroll.is_primary = False
        enroll.save()
        moved += 1
    counts["curricula"] = moved
    counts["curricula_duplicates_removed"] = removed


__all__ = [
    "StudentMergeConflictT",
    "StudentMergeResultT",
    "safe_merge_student",
]
