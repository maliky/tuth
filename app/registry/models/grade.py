"""Grade records for completed course sections."""

from typing import Self

from app.registry.choices import GradeChoice
from django.db import models
from simple_history.models import HistoricalRecords

from app.registry.constants import GRADES_DESCRIPTION, GRADES_NUM


class GradeValue(models.Model):
    """A class to define the different Grade types."""

    # ~~~~~~~~ Mandatory ~~~~~~~~
    code = models.CharField(choices=GradeChoice.choices, default=GradeChoice.IP, unique=True)
    # ~~~~ Auto-filled ~~~~
    number = models.PositiveSmallIntegerField(null=True, default=GRADES_NUM["IP"])
    description = models.CharField(
        max_length=60, null=True, default=GRADES_DESCRIPTION["IP"]
    )
    history = HistoricalRecords()

    def __str__(self):
        return self.code

    def _ensure_number(self):
        """Make sure a number is defined for a Grade."""
        if not self.number:
            self.number = GRADES_NUM[self.code.upper()]

    def _ensure_description(self):
        """Make sure a number is defined for a Grade."""
        if not self.description:
            self.description = GRADES_DESCRIPTION[self.code]

    def save(self, *args, **kwargs) -> None:
        """Enforcing a number and a description before saving."""
        self._ensure_number()
        self._ensure_description()
        super().save(*args, **kwargs)

    @classmethod
    def get_default(cls) -> Self:
        """Return a default Grade, IP."""
        def_grd, _ = cls.objects.get_or_create(code="IP")
        return def_grd

    class Meta:
        ordering = ["-number", "code"]


class Grade(models.Model):
    """Letter/numeric grade awarded to a student for a Section.

    Example:
        >>> from app.registry.models.grade import Grade
        >>> Grade.objects.create(
        ...     student=student_profile,   # check test factories
        ...     section=section_factory(1),
        ...     grade="A",
        ... )
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    student = models.ForeignKey("people.Student", on_delete=models.CASCADE)
    section = models.ForeignKey("timetable.Section", on_delete=models.CASCADE)
    value = models.ForeignKey("registry.GradeValue", on_delete=models.CASCADE, null=True)

    # ~~~~ Auto-filled ~~~~
    graded_on = models.DateField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        unique_together = ("student", "section")

    def __str__(self) -> str:  # pragma: no cover
        """Human readable representation used in admin lists."""
        return f"{self.student} – {self.section}: {self.value}"

    def number(self):
        """Return the grade number."""
        if self.value:
            return self.value.number

    def code(self):
        """Return the grade code or letter."""
        if self.value:
            return self.value.code
