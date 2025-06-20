"""Scholarship module."""

from __future__ import annotations

from django.db import models


class Scholarship(models.Model):
    """Financial aid linking a donor to a student.

    Scholarships can reduce a student's balance in their
    :class:~app.finance.models.FinancialRecord through custom business logic.
    No signals are attached by default.

    Attributes:
        donor (people.Donor): Person or organization funding the scholarship.
        student (people.Student): Recipient of the aid.
        amount (Decimal): Monetary value of the scholarship.
        start_date (date): When the scholarship becomes active.
        end_date (date): Optional expiration date.
        conditions (str): Extra eligibility notes.

    Example:
        >>> from decimal import Decimal
        >>> from datetime import date
        >>> Scholarship.objects.create(
        ...     donor=donor,
        ...     student=student_profil,
        ...     amount=Decimal("100.00"),
        ...     start_date=date.today(),
        ... )
    """

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
        """Return "donor -> student" for readability in admin screens."""
        return f"{self.donor} -> {self.student}"
