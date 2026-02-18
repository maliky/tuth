"""Grade records for completed course sections."""

from typing import Self, cast

from app.registry.choices import GradeChoice
from django.db import models
from simple_history.models import HistoricalRecords

from app.registry.constants import GRADES_DESCRIPTION, GRADES_NUM


class GradeValue(models.Model):
    """A class to define the different Grade types."""

    DEFAULT_VALUES: list[tuple[str, int]] = [
        ("ab", 0),
        ("b", 3),
        ("c", 2),
        ("d", 1),
        ("dr", 0),
        ("f", 0),
        ("i", 0),
        ("ip", 0),
        ("ng", 0),
        ("w", 0),
        ("a", 4),
    ]

    # ~~~~~~~~ Mandatory ~~~~~~~~
    code = models.CharField(
        choices=GradeChoice.choices, default=GradeChoice.IP, unique=True
    )
    # ~~~~ Auto-filled ~~~~
    number = models.PositiveSmallIntegerField(null=True, default=GRADES_NUM["ip"])
    description = models.CharField(
        max_length=60, null=True, default=GRADES_DESCRIPTION["ip"]
    )
    info = models.TextField(blank=True, default="")
    history = HistoricalRecords()

    @classmethod
    def _populate_attributes_and_db(cls):
        """Create a row for each var in DEFAULT_VALUES and create subclass attributes."""
        # This method is temporary
        for _code, _num in cls.DEFAULT_VALUES:
            obj, _ = cls.objects.get_or_create(
                code=_code,
                defaults={"description": GRADES_DESCRIPTION[_code]},
            )

    def __str__(self):
        """Return the grade code in uppercase for admin displays."""
        return (self.code or "").upper()

    def _normalize_code(self):
        """Store grade codes in lowercase to match constants/lookups."""
        if self.code:
            self.code = self.code.lower()

    def _ensure_number(self):
        """Make sure a number is defined for a Grade."""
        if not self.number:
            self.number = GRADES_NUM[self.code]

    def _ensure_description(self):
        """Make sure a number is defined for a Grade."""
        if not self.description:
            self.description = GRADES_DESCRIPTION[self.code]

    def save(self, *args, **kwargs) -> None:
        """Enforcing a number and a description before saving."""
        self._normalize_code()
        self._ensure_number()
        self._ensure_description()
        super().save(*args, **kwargs)

    @classmethod
    def get_dft(cls) -> Self:
        """Return a default Grade, IP."""
        def_grd, _ = cls.objects.get_or_create(code="ip")
        return cast(Self, def_grd)

    class Meta:
        ordering = ["-number", "code"]


class Grade(models.Model):
    """Letter/numeric grade awarded to a student for a Section.

    Example:
        >>> from app.registry.models.grade import Grade
        >>> Grade.objects.create(
        ...     student=student_profile,   # check test factories
        ...     section=sec_factory(1),
        ...     grade="A",
        ... )
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    student = models.ForeignKey("people.Student", on_delete=models.CASCADE)
    # Keep grade rows immutable from section/curriculum cleanup operations.
    section = models.ForeignKey("timetable.Section", on_delete=models.PROTECT)
    value = models.ForeignKey("registry.GradeValue", on_delete=models.CASCADE, null=True)
    # Tracks which attempt should be used by policy consumers (prereq/GPA views).
    is_effective = models.BooleanField(default=True, db_index=True)
    # Free-form audit notes for merge/reconciliation operations.
    info = models.TextField(blank=True, default="")

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
