"""Section module."""

from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models
from .semester import Semester


class Section(models.Model):
    """Scheduled instance of a course in a specific semester."""

    number = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    course = models.ForeignKey(
        "academics.Course", related_name="sections", on_delete=models.PROTECT
    )
    semester = models.ForeignKey(Semester, on_delete=models.PROTECT)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    schedule = models.ForeignKey(
        Schedule, on_delete=models.PROTECT, related_name="schedule"
    )

    # to be defined by Admin & VPA
    max_seats = models.PositiveIntegerField(default=30, validators=[MinValueValidator(3)])
    current_registrations = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course", "semester", "number"],
                name="uniq_section_per_course_semester",
            )
        ]
        ordering = ["semester", "course", "number"]

    # ---------- display helpers ----------
    @property
    def short_code(self) -> str:
        return f"{self.course.code}:s{self.number}"

    @property
    def long_code(self) -> str:
        return f"{self.semester} {self.short_code}"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.long_code} | {self.room}"

    def has_available_seats(self) -> bool:
        """Return 'True' if the section still has seats available."""
        return self.current_registrations < self.max_seats
