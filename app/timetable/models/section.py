"""Section module."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from django.core.validators import MinValueValidator
from django.db import models

if TYPE_CHECKING:
    from app.spaces.models import Room


class Section(models.Model):
    """
    A single course‐offering in a given Semester.
    We’ll now allow each Section to have multiple Schedule rows.
    """

    number = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    semester = models.ForeignKey("timetable.Semester", on_delete=models.PROTECT)
    course = models.ForeignKey(
        "academics.Course", related_name="sections", on_delete=models.PROTECT
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    current_registrations = models.PositiveIntegerField(default=0, editable=False)
    faculty = models.ForeignKey(
        "people.FacultyProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="faculty",
        # limit_choices_to={
        #     "user__role_assignments__role__in": [
        #         "faculty",
        #         "lecturer",
        #         "assistant_professor",
        #         "dean",
        #         "chair",
        #         "associate_professor",
        #         "professor",
        #         "vpaa",
        #     ]
        # },
    )
    # to be defined by Admin & VPA
    max_seats = models.PositiveIntegerField(default=30, validators=[MinValueValidator(3)])

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
    def spaces(self) -> List[Room]:
        """
        Return a list of all Room instances in which this section meets.
        """
        # “schedules” is the related_name on Schedule → Section
        return [s.room for s in self.schedules.all() if s.room]

    @property
    def space_codes(self) -> str:
        """
        Return a comma-separated string of each Room’s code.
        """
        return ", ".join(room.code for room in self.spaces)

    @property
    def short_code(self) -> str:
        return f"{self.course.code}:s{self.number}"

    @property
    def long_code(self) -> str:
        return f"{self.semester} {self.short_code}"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.long_code} | {self.space_codes}"

    def has_available_seats(self) -> bool:
        """Return 'True' if the section still has seats available."""
        return self.current_registrations < self.max_seats

    def clean(self) -> None:
        """Check that the date are correct"""
        if self.end_date is not None:
            if self.start_date:
                assert self.start_date < self.end_date
