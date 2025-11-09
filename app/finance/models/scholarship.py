"""Scholarship module."""

from __future__ import annotations

from django.db import models
from simple_history.models import HistoricalRecords


def template_upload_path(instance, filename):
    """Return storage path for donor letter templates."""
    donor = instance.donor_id or "generic"
    return f"scholarship/templates/{donor}/{filename}"


class ScholarshipLetterTemplate(models.Model):
    """Reusable document templates for donor letters."""

    donor = models.ForeignKey(
        "people.Donor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="letter_templates",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    template_file = models.FileField(upload_to=template_upload_path)
    placeholders = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:  # pragma: no cover
        donor = self.donor or "Generic"
        return f"{donor} – {self.name}"


class Scholarship(models.Model):
    """Financial aid linking a donor to a student.

    Scholarships can reduce a student's balance in their
    :class:~app.finance.models.Payment through custom business logic.
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

    # ~~~~~~~~ Mandatory ~~~~~~~~
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
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()

    # ~~~~~~~~ Optional ~~~~~~~~
    end_date = models.DateField(null=True, blank=True)
    conditions = models.TextField(blank=True)
    letter_template = models.ForeignKey(
        "finance.ScholarshipLetterTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scholarships",
    )

    def __str__(self) -> str:  # pragma: no cover
        """Return "donor -> student" for readability in admin screens."""
        return f"{self.donor} -> {self.student}"


class ScholarshipTermSnapshot(models.Model):
    """Stores per-semester GPA data used for scholarship compliance."""

    student = models.ForeignKey(
        "people.Student",
        on_delete=models.CASCADE,
        related_name="scholarship_snapshots",
    )
    semester = models.ForeignKey(
        "timetable.Semester",
        on_delete=models.CASCADE,
        related_name="scholarship_snapshots",
    )
    gpa = models.DecimalField(max_digits=4, decimal_places=2)
    credits_attempted = models.PositiveSmallIntegerField()
    credits_completed = models.PositiveSmallIntegerField()
    awards_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "semester")
        ordering = ["-semester__academic_year__start_date", "-semester__number"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.student} – {self.semester}: {self.gpa}"
