"""Scholarship module."""

from __future__ import annotations

from django.db import models


class Scholarship(models.Model):
    """Financial aid linking a donor to a student."""

    donor = models.ForeignKey(
        "people.Donor",
        on_delete=models.CASCADE,
        related_name="scholarships",
    )
    student = models.ForeignKey(
        "people.Student",
        on_delete=models.CASCADE,
        related_name="scholarships",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    conditions = models.TextField(blank=True)

    def __str__(self) -> str:  # pragma: no cover
        """Return ``"donor -> student"`` for readability in admin screens."""
        return f"{self.donor} -> {self.student}"
