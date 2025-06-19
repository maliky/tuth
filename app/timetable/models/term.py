"""Term module."""

from __future__ import annotations
from django.db import models
from django.core.exceptions import ValidationError

from app.shared.enums import TERM_NUMBER
from app.timetable.utils import validate_subperiod


class Term(models.Model):
    """One of the sub-periods that divide a semester.

    Example:
        >>> from app.timetable.models import Term
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
        if container_start is None or container_end is None:
            raise ValidationError("Parent semester must have start and end dates")

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
