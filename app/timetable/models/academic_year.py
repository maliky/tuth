"""Academic year module."""

from __future__ import annotations

from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import ExtractYear
from simple_history.models import HistoricalRecords



class AcademicYear(models.Model):
    """Top-level period covering two consecutive semesters.

    Example:
        >>> AcademicYear.objects.create(start_date=date(2025, 9, 1))

    Side Effects:
        save() computes code and long_name.
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    start_date = models.DateField(unique=True)
    end_date = models.DateField(unique=True, blank=True)
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()

    # ~~~~ Read-only ~~~~
    code = models.CharField(max_length=5, editable=False, unique=True)
    long_name = models.CharField(max_length=9, editable=False, unique=True)

    def __str__(self) -> str:  # pragma: no cover
        return self.long_name

    def clean(self) -> None:
        """Ensure start and end dates form a valid academic year."""
        st = self.start_date

        if st.month not in (7, 8, 9, 10):
            raise ValidationError("Start date must be in July–October.")

        if self.end_date:
            assert self.end_date.year > st.year
        else:
            # the day *before* next academic year starts
            self.end_date = self.start_date.replace(year=st.year + 1) - timedelta(days=1)

    def save(self, *args, **kwargs) -> None:
        """Populate derived fields long_name and code before saving."""
        # setting a default for the end_year
        ys = self.start_date.year

        if self.start_date and not self.end_date:
            # the day *before* next academic year starts
            self.end_date = self.start_date.replace(year=ys + 1) - timedelta(days=1)

        ye = ys + 1
        self.long_name = f"{ys}-{ye}"
        self.code = f"{str(ys)[-2:]}-{str(ye)[-2:]}"

        super().save(*args, **kwargs)

    @classmethod
    def get_default(cls, today: date | None = None) -> "AcademicYear":
        """Return the current academic year.

        Uses Aug 1 as the rollover: dates on/after Aug 1 belong to the new academic year,
        dates before Aug 1 belong to the prior start year.
        """
        ref = today or date.today()
        start_year = ref.year if ref.month >= 8 else ref.year - 1
        start = date(start_year, 8, 1)
        ay, _ = cls.objects.get_or_create(start_date=start)
        return ay

    class Meta:
        constraints = [
            models.UniqueConstraint(
                ExtractYear("start_date"),
                name="uniq_academic_year_by_year",
            )
        ]
        ordering = ["-start_date"]
