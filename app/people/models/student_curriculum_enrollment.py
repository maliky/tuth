"""Through model linking students to one or more curricula."""

from __future__ import annotations

from datetime import date

from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords


class StudentCurriculumEnrollment(models.Model):
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
