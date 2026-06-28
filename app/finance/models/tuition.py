"""Career-aware tuition rate policy."""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from simple_history.models import HistoricalRecords

from app.academics.choices import AcademicCareer


class TuitionRate(models.Model):
    """Tuition rate for one academic career in one semester."""

    semester = models.ForeignKey(
        "timetable.Semester",
        on_delete=models.PROTECT,
        related_name="tuition_rates",
    )
    academic_career = models.CharField(
        max_length=20,
        choices=AcademicCareer.choices,
        default=AcademicCareer.UNDERGRADUATE,
        db_index=True,
    )
    currency = models.CharField(max_length=8, default="USD")
    tuition_per_credit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("5.00"),
    )
    foreigner_tuition_per_credit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("25.00"),
    )
    source = models.CharField(max_length=120, blank=True)
    history = HistoricalRecords()

    def __str__(self) -> str:  # pragma: no cover
        """Return a readable tuition-rate label."""
        return f"{self.semester} {self.academic_career}: {self.tuition_per_credit}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["semester", "academic_career"],
                name="uniq_tuition_rate_per_semester_career",
            )
        ]
        ordering = ["-semester__start_date", "academic_career"]
