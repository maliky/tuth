from __future__ import annotations

from app.shared.constants.choices import StatusRegistration
from django.core.validators import MinValueValidator
from django.db import models

from .semester import Semester


class Section(models.Model):
    """Scheduled instance of a course in a specific semester."""

    course = models.ForeignKey(
        "academics.Course", related_name="sections", on_delete=models.PROTECT
    )
    number = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    semester = models.ForeignKey(Semester, on_delete=models.PROTECT)
    faculty = models.ForeignKey(
        "people.FacultyProfile",
        null=True,
        blank=True,
        limit_choices_to={"role_assignments__role": "Instructor"},
        on_delete=models.SET_NULL,
    )
    # could try lasy reference
    room = models.ForeignKey(
        "spaces.Room", null=True, blank=True, on_delete=models.SET_NULL
    )
    # à voir plus tard, schedule ?  22/05/2025
    schedule = models.CharField(max_length=100, blank=True)

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
        ordering = ["semester__academic_year__start_date", "course__name"]

    # ---------- display helpers ----------
    @property
    def short_code(self) -> str:
        return f"{self.course.code}:s{self.number}"

    @property
    def long_code(self) -> str:
        return f"{self.semester} {self.short_code}"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.long_code} | {self.room}"

    def has_available_seats(self):
        """Return 'True' if the section still has seats available."""
        return self.current_registrations < self.max_seats
