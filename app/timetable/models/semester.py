"""Semester module."""

from __future__ import annotations
from django.db import models
from app.timetable.choices import SEMESTER_NUMBER
from app.timetable.utils import validate_subperiod


class Semester(models.Model):
    """Major section of academic year (e.g. semester 1, 2 or 3 vacations).

    Example:
        >>> from app.timetable.models import Semester
        >>> Semester.objects.create(academic_year=year, number=1)
    """

    academic_year = models.ForeignKey("timetable.AcademicYear", on_delete=models.PROTECT)
    number = models.PositiveSmallIntegerField(
        choices=SEMESTER_NUMBER.choices, help_text="Semester number"
    )
    # > Could be interesting to set this to the academic_year start date automaticaly on save
    # > and force non null values.
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def clean(self) -> None:
        "Checking that the start and end date of the Semester are within the academic years dates"
        # Semester.clean() and Term.clean() call validate_subperiod() but not
        # full_clean() on related objects. In admin workflows the parent may still
        # carry invalid dates. Consider a parent-before-child save order or
        # database-level CHECK constraints.
        validate_subperiod(
            sub_start=self.start_date,
            sub_end=self.end_date,
            container_start=self.academic_year.start_date,
            container_end=self.academic_year.end_date,
            overlap_qs=Semester.objects.filter(academic_year=self.academic_year).exclude(
                pk=self.pk
            ),
            overlap_message="Overlapping Semesters in the same academic year.",
            label="semester",
        )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "number"], name="uniq_semester_per_year"
            )
        ]
        ordering = ["start_date"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.academic_year.code}_Sem{self.number}"
