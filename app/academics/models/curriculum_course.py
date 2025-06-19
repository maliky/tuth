"""Curriculum course module."""

from __future__ import annotations

from django.db import models

from app.academics.choices import CREDIT_NUMBER


class CurriculumCourse(models.Model):
    """Map :class:`Curriculum` instances to their constituent courses.

    Example:
        >>> from app.academics.models import CurriculumCourse
        >>> CurriculumCourse.objects.create(curriculum=curriculum, course=course)

    Side Effects:
        ``save()`` defaults ``credit_hours`` to the course value when missing.
    """

    curriculum = models.ForeignKey(
        "academics.Curriculum", on_delete=models.CASCADE, related_name="programme_lines"
    )
    course = models.ForeignKey(
        "academics.Course", on_delete=models.CASCADE, related_name="programme_lines"
    )
    is_required = models.BooleanField(default=True)

    # This is here because it can vary per curricula
    credit_hours = models.PositiveSmallIntegerField(
        choices=CREDIT_NUMBER.choices,
        null=True,
        blank=True,
        help_text="Credits to be used in this curriculum for this course",
    )

    @property
    def effective_credit_hours(self) -> int:
        """
        Credits to show on transcripts: curriculum override -or-
        fallback to the catalogue value.
        """
        return (
            self.credit_hours
            if self.credit_hours is not None
            else self.course.credit_hours
        )

    def __str__(self) -> str:  # pragma: no cover
        """Return ``Curriculum <-> Course`` for readability."""
        return f"{self.curriculum} <-> {self.course}"

    def save(self, *args, **kwargs) -> None:
        """Default ``credit_hours`` to the course value when unset."""
        if self.credit_hours is None:
            self.credit_hours = self.course.credit_hours

        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("curriculum", "course"), name="uniq_course_per_curriculum"
            )
        ]
        ordering = ["curriculum"]
