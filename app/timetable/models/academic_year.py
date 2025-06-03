"""Academic year module."""

from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import ExtractYear


class AcademicYear(models.Model):
    """Top-level period covering two consecutive semesters."""

    start_date = models.DateField(unique=True)
    end_date = models.DateField(unique=True)
    long_name = models.CharField(max_length=9, editable=False, unique=True)
    short_name = models.CharField(max_length=5, editable=False, unique=True)

    def clean(self) -> None:
        if self.start_date.month not in (7, 8, 9, 10):
            raise ValidationError("Start date must be in July–October.")

    def save(self, *args, **kwargs) -> None:
        ys = self.start_date.year

        if self.start_date and not self.end_date:
            # the day *before* next academic year starts
            self.end_date = self.start_date.replace(year=ys + 1) - timedelta(days=1)

        ye = ys + 1
        self.long_name = f"{ys}/{ye}"
        self.short_name = f"{str(ys)[-2:]}-{str(ye)[-2:]}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover
        return self.long_name

    class Meta:
        constraints = [
            models.UniqueConstraint(
                ExtractYear("start_date"),
                name="uniq_academic_year_by_year",
            )
        ]
        ordering = ["-start_date"]
