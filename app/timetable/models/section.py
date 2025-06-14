"""Section module."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from django.core.validators import MinValueValidator
from django.db import models

if TYPE_CHECKING:
    from app.spaces.models import Room


class Section(models.Model):
    """
    A single course offering in a given semester.
    A section can include multiple session rows.
    """

    semester = models.ForeignKey("timetable.Semester", on_delete=models.PROTECT)
    course = models.ForeignKey("academics.Course", on_delete=models.PROTECT)
    number = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    faculty = models.ForeignKey(
        "people.Faculty",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    current_registrations = models.PositiveIntegerField(default=0, editable=False)
    # to be defined by Admin & VPA
    max_seats = models.PositiveIntegerField(default=30, validators=[MinValueValidator(3)])

    # ---------- display helpers ----------
    @property
    def spaces(self) -> List[Room]:
        """
        Return a list of all Room instances in which this section meets.
        """
        return [s.room for s in self.sessions.all() if s.room]

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

    # compatibility aliases -------------------------------------------------
    @property
    def instructor_id(self):
        """Return the associated faculty id."""
        return self.faculty_id

    @property
    def room_id(self):
        """Return the room id of the first session if any."""
        first = self.sessions.first()
        return first.room_id if first else None

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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["semester", "course", "number", "faculty"],
                name="uniq_section_per_course_faculty",
            )
        ]
        indexes = [
            models.Index(fields=["semester", "course"]),
            models.Index(fields=["semester", "course", "number"]),
            models.Index(fields=["semester", "course", "number", "faculty"]),
        ]
        ordering = ["semester", "course", "number"]
