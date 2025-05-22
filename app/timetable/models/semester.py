from __future__ import annotations
from django.db import models
from app.shared.enums import SEMESTER_NUMBER
from app.timetable.utils import validate_subperiod


class Semester(models.Model):
    academic_year = models.ForeignKey(
        "timetable.AcademicYear", on_delete=models.PROTECT, related_name="semesters"
    )
    number = models.PositiveSmallIntegerField(
        choices=SEMESTER_NUMBER.choices, help_text="Semester number"
    )
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
        return f"{self.academic_year.short_name}_Sem{self.number}"
