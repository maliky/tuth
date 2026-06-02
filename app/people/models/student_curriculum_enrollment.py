"""Through model linking students to one or more curricula."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, TypeAlias, cast

from django.db import models, transaction
from django.db.models import Q
from simple_history.models import HistoricalRecords

from app.academics.models.curriculum import Curriculum

if TYPE_CHECKING:
    from app.people.models.student import Student


StdCurriEnrollT: TypeAlias = "StdCurriEnroll | None"


class StdCurriEnroll(models.Model):
    """Enrollment link between a student and a curriculum."""

    student = models.ForeignKey(
        "people.Student",
        on_delete=models.CASCADE,
        related_name="curriculum_enrollments",
    )
    curriculum = models.ForeignKey(
        "academics.Curriculum",
        on_delete=models.CASCADE,
        related_name="student_enrollments",
    )
    entry_semester = models.ForeignKey(
        "timetable.Semester",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="student_curriculum_enrollments_started",
    )
    exit_semester = models.ForeignKey(
        "timetable.Semester",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="student_curriculum_enrollments_ended",
    )
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    creation_date = models.DateField(default=date.today)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def __str__(self) -> str:
        """Return a compact label for admin displays."""
        return f"{self.student} -> {self.curriculum}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "curriculum"],
                name="uniq_student_curriculum_enrollment",
            ),
            models.UniqueConstraint(
                fields=["student"],
                condition=Q(is_primary=True),
                name="uniq_primary_curriculum_enrollment_per_student",
            ),
        ]


def _std_curri_enroll_qs(student: "Student") -> models.QuerySet[StdCurriEnroll]:
    """Return enrollment rows ordered by stable priority."""
    return StdCurriEnroll.objects.filter(student=student).select_related("curriculum")


def get_primary_std_curri_enroll(student: "Student") -> StdCurriEnrollT:
    """Return one canonical enrollment row for the student."""
    cached = cast(
        StdCurriEnrollT,
        getattr(student, "_primary_std_curri_enroll_cache", None),
    )
    if cached is not None:
        return cached
    enroll = (
        _std_curri_enroll_qs(student)
        .order_by("-is_primary", "-is_active", "-updated_at", "-id")
        .first()
    )
    student._primary_std_curri_enroll_cache = enroll  # type: ignore[attr-defined]
    return enroll


def get_primary_curriculum(student: "Student") -> Curriculum:
    """Return the curriculum selected by enrollment precedence."""
    enroll = get_primary_std_curri_enroll(student)
    if enroll is not None:
        return enroll.curriculum
    return Curriculum.get_dft()


def set_primary_std_curri_enroll(
    student: "Student",
    curriculum: Curriculum,
    *,
    entry_semester_id: int | None = None,
    is_active: bool = True,
) -> StdCurriEnroll:
    """Ensure one primary enrollment row for the provided curriculum."""
    with transaction.atomic():
        enroll = StdCurriEnroll.objects.filter(
            student=student,
            curriculum=curriculum,
        ).first()
        if enroll is None:
            # The partial unique constraint allows only one primary row per student.
            StdCurriEnroll.objects.filter(student=student, is_primary=True).update(
                is_primary=False
            )
            enroll = StdCurriEnroll.objects.create(
                student=student,
                curriculum=curriculum,
                entry_semester_id=entry_semester_id,
                is_primary=True,
                is_active=is_active,
            )
            student._primary_std_curri_enroll_cache = enroll  # type: ignore[attr-defined]
            return enroll

        if not enroll.is_primary:
            # Demote existing primary rows first to preserve the unique primary constraint.
            StdCurriEnroll.objects.filter(student=student, is_primary=True).exclude(
                pk=enroll.pk
            ).update(is_primary=False)

        update_fields: list[str] = []
        if not enroll.is_primary:
            enroll.is_primary = True
            update_fields.append("is_primary")
        if enroll.is_active != is_active:
            enroll.is_active = is_active
            update_fields.append("is_active")
        if entry_semester_id and enroll.entry_semester_id != entry_semester_id:
            enroll.entry_semester_id = entry_semester_id
            update_fields.append("entry_semester")
        if update_fields:
            enroll.save(update_fields=update_fields)

        StdCurriEnroll.objects.filter(student=student, is_primary=True).exclude(
            pk=enroll.pk
        ).update(is_primary=False)

    student._primary_std_curri_enroll_cache = enroll  # type: ignore[attr-defined]
    return enroll


def sync_primary_std_curri_enroll(student: "Student") -> StdCurriEnroll:
    """Ensure one canonical primary enrollment row exists for the student."""
    enroll = get_primary_std_curri_enroll(student)
    if enroll is None:
        return set_primary_std_curri_enroll(
            student,
            Curriculum.get_dft(),
            entry_semester_id=student.entry_semester_id,
            is_active=True,
        )
    return set_primary_std_curri_enroll(
        student,
        enroll.curriculum,
        entry_semester_id=student.entry_semester_id or enroll.entry_semester_id,
        is_active=enroll.is_active,
    )
