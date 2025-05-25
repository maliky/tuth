from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models


class Prerequisite(models.Model):
    """Relationship describing that one course must precede another."""

    course = models.ForeignKey(
        "academics.Course", related_name="course_prereq_edges", on_delete=models.CASCADE
    )
    prerequisite_course = models.ForeignKey(
        "academics.Course", related_name="required_for_edges", on_delete=models.CASCADE
    )
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
                check=~models.Q(course=models.F("prerequisite_course")),
                name="no_self_prerequisite",
            ),
        ]
