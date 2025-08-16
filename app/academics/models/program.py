"""Curriculum course module."""

from __future__ import annotations

from typing import Optional, Self

from app.shared.models import CreditHour
from django.db import models
from simple_history.models import HistoricalRecords

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
    credit_hours = models.ForeignKey(
        "shared.CreditHour",
        on_delete=models.PROTECT,
        default=3,
        help_text="Credits to be used in this curriculum for this course",
        related_name="programs",
    )

    def __str__(self) -> str:  # pragma: no cover
        """Return Curriculum <-> Course for readability."""
        return f"{self.course} <-> {self.curriculum}"

    def _ensure_credit_hours(self):
        """Make sure the credit_hours is set."""
        if not self.credit_hours_id:
            self.credit_hours_id = 3
        CreditHour.objects.get_or_create(
            code=self.credit_hours_id, defaults={"label": str(self.credit_hours_id)}
        )

    def save(self, *args, **kwargs):
        """Make sure we set default before saving."""
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
