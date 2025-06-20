"""Term module."""

from __future__ import annotations
from django.db import models

from app.timetable.choices import TERM_NUMBER
from app.timetable.utils import validate_subperiod


class Term(models.Model):
    """One of the sub-periods that divide a semester.

    Example:
        >>> Term.objects.create(semester=semester, number=1)
    """

    semester = models.ForeignKey(
        "timetable.Semester", on_delete=models.PROTECT, related_name="terms"
    )
    number = models.PositiveSmallIntegerField(
        choices=TERM_NUMBER.choices, help_text="Term number"
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def clean(self) -> None:
        """Validate dates are inside the parent semester and do not overlap."""
        container_start = self.semester.start_date
        container_end = self.semester.end_date
        assert container_start is not None and container_end is not None

        validate_subperiod(
            sub_start=self.start_date,
            sub_end=self.end_date,
            container_start=container_start,
            container_end=container_end,
            overlap_qs=Term.objects.filter(semester=self.semester).exclude(pk=self.pk),
            overlap_message="Overlapping terms in the same semester.",
            label="term",
        )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["semester", "number"], name="uniq_term_per_semester"
            )
        ]
        ordering = ["start_date", "number"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.semester}T{self.number}"
