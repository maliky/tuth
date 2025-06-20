"""Curriculum course module."""

from __future__ import annotations

from django.db import models

from app.academics.choices import CREDIT_NUMBER


class Program(models.Model):
    """Map Curriculum instances to their constituent courses.

    Example:
        >>> Program.objects.create(curriculum=curriculum, course=course)

    Side Effects:
        save() defaults credit_hours to the course value when missing.
    """

    curriculum = models.ForeignKey(
        "academics.Curriculum", on_delete=models.CASCADE, related_name="courses"
    )
    course = models.ForeignKey(
        "academics.Course", on_delete=models.CASCADE, related_name="curricula"
    )
    is_required = models.BooleanField(default=True)

    # credit hours depend on the curricula not the Course, so It moved from course to here.
    credit_hours = models.PositiveSmallIntegerField(
        choices=CREDIT_NUMBER.choices,
        help_text="Credits to be used in this curriculum for this course",
        default=CREDIT_NUMBER.THREE,
    )

    def __str__(self) -> str:  # pragma: no cover
        """Return Curriculum <-> Course for readability."""
        return f"{self.curriculum} <-> {self.course}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("curriculum", "course"), name="uniq_course_per_curriculum"
            )
        ]
        ordering = ["curriculum"]
