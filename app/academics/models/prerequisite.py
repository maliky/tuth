"""Prerequisite module."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords


class Prerequisite(models.Model):
    """Relationship describing that one course must precede another.

    Example:
        >>> Prerequisite.objects.create(course=course, prerequisite_course=other_course)

    Side Effects:
        clean() prevents circular dependencies.
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    course = models.ForeignKey(
        "academics.Course", related_name="course_prereq_edges", on_delete=models.CASCADE
    )
    prerequisite_course = models.ForeignKey(
        "academics.Course", related_name="required_for_edges", on_delete=models.CASCADE
    )
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()

    # ~~~~~~~~ Optional ~~~~~~~~
    curriculum = models.ForeignKey(
        "academics.Curriculum",
        on_delete=models.CASCADE,
        related_name="prerequisites",
        null=True,
        blank=True,
    )

    def clean(self) -> None:
        """Prevent reciprocal prerequisites that would create a cycle."""
        if Prerequisite.objects.filter(
            course=self.prerequisite_course, prerequisite_course=self.course
        ).exists():
            raise ValidationError("Circular prerequisite detected.")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["curriculum", "course", "prerequisite_course"],
                name="uniq_prerequisite_per_curriculum",
            ),
            models.CheckConstraint(
                condition=~models.Q(course=models.F("prerequisite_course")),
                name="no_self_prerequisite",
            ),
        ]
