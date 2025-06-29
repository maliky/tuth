"""Section module."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from app.academics.models.curriculum import Curriculum
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from app.academics.models.course import Course

if TYPE_CHECKING:
    from app.spaces.models.core import Room


class Section(models.Model):
    """A single course offering in a given semester.

    A section can include multiple session rows or schedule.
    Eg. MATH101 by M. Koné 25-26 (section) on Mondays and Thursday (sessions)

    Example:
        >>> from app.timetable.models import Section
        >>> Section.objects.create(course=course, semester=semester, number=1)

        >>> Section.objects.create(course=course, semester=semester)

    Side Effects:
        Section numbers auto-increment
    """

    # ~~~~ Mandatory ~~~~
    semester = models.ForeignKey("timetable.Semester", on_delete=models.PROTECT)
    program = models.ForeignKey(
        "academics.Program", on_delete=models.CASCADE, related_name="sections"
    )
    number = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    # ~~~~ Optional ~~~~
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

    def __str__(self) -> str:  # pragma: no cover
        """Return a human readable identifier with allocated rooms."""
        return f"{self.short_code} | {self.space_codes}"

    @property
    def course(self) -> Course:
        """Return the Course associated with the program of this section."""
        course = self.program.course
        if not course.id:
            raise ValidationError("Course must be set for this property.")
        return course

    @property
    def curriculum(self) -> Curriculum:
        """Return the Curriculum associated with the program of this section."""
        curriculum = self.program.curriculum
        if not curriculum.id:
            raise ValidationError("Curriculum must be set for this property.")

        return curriculum

    @property
    def spaces(self) -> List[Room]:
        """Return a list of all Room instances in which this section meets."""
        return [s.room for s in self.sessions.all() if s.room]

    @property
    def space_codes(self) -> str:
        """Return a comma-separated string of each room’s code."""
        return ", ".join(room.code for room in self.spaces)

    @property
    def short_code(self) -> str:
        """Shorthand used for slugging the section in URLs or logs."""
        return f"{self.course.code}:s{self.number}"

    @property
    def long_code(self) -> str:
        """Combine semester code and short_code for uniqueness."""
        return f"{self.semester} {self.short_code}"

    @property
    def available_seats(self) -> int:
        """Return the number of seats available."""
        return (
            self.max_seats - self.current_registrations
            if self.has_available_seats()
            else 0
        )

    def has_available_seats(self) -> bool:
        """Return 'True' if the section still has seats available."""
        return self.current_registrations < self.max_seats

    def clean(self) -> None:
        """Check that the dates are correct."""
        if self.end_date is not None:
            if self.start_date:
                assert self.start_date < self.end_date

    class Meta:
        # May Move this to manual in Save check because does not hold for default programs
        constraints = [
            models.UniqueConstraint(
                fields=["semester", "program", "number"],
                name="uniq_section_per_program",
            )
        ]
        indexes = [
            models.Index(fields=["semester", "program"]),
            models.Index(fields=["semester", "program", "number"]),
        ]
        ordering = ["semester", "program", "number"]
