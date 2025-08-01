"""Curriculum course module."""

from __future__ import annotations

from typing import Optional, Self

from django.db import models
from simple_history.models import HistoricalRecords

from app.academics.choices import CREDIT_NUMBER
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum


class Program(models.Model):
    """Map Curriculum instances to their constituent courses.

    Example:
        >>> Program.objects.create(curriculum=curriculum, course=course)

    Side Effects:
        save() defaults credit_hours to the course value when missing.
    """

    # ~~~~ Mandatory ~~~~
    # curriculum or major
    curriculum = models.ForeignKey(
        "academics.Curriculum", on_delete=models.CASCADE, related_name="programs"
    )
    course = models.ForeignKey(
        "academics.Course", on_delete=models.CASCADE, related_name="in_programs"
    )

    # ~~~~ Auto-filled ~~~~
    is_required = models.BooleanField(default=False)  # for required general courses
    is_elective = models.BooleanField(default=False)
    history = HistoricalRecords()
    # credit hours depend on the curricula not the Course
    credit_hours = models.PositiveSmallIntegerField(
        choices=CREDIT_NUMBER.choices,
        help_text="Credits to be used in this curriculum for this course",
        default=CREDIT_NUMBER.THREE,
    )

    def __str__(self) -> str:  # pragma: no cover
        """Return Curriculum <-> Course for readability."""
        return f"{self.course} <-> {self.curriculum}"

    def _ensure_credit_hours(self):
        """Make sure the credit_hours is set."""
        if not self.credit_hours:
            self.credit_hours = CREDIT_NUMBER.THREE

    def save(self, *args, **kwargs):
        """Make sure we set default before saving."""
        if not self.credit_hours:
            self._ensure_credit_hours()
        super().save(*args, **kwargs)

    @classmethod
    def get_default(cls, _course: Optional[Course] = None) -> Self:
        """Returns a default Program."""
        def_pg, _ = cls.objects.get_or_create(
            curriculum=Curriculum.get_default(),
            course=(_course or Course.get_default()),
        )
        return def_pg

    @classmethod
    def get_unique_default(cls) -> Self:
        """Returns a default unique Program."""
        u_course = Course.get_unique_default()
        return cls.get_default(_course=u_course)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("curriculum", "course"), name="uniq_course_per_curriculum"
            )
        ]
        ordering = ["curriculum"]
