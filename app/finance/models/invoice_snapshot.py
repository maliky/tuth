"""Snapshot model for printable invoices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models
from simple_history.models import HistoricalRecords

if TYPE_CHECKING:
    from app.people.models.staffs import Staff


class InvoiceSnapshot(models.Model):
    """Immutable snapshot of invoice lines for PDF rendering.

    A snapshot captures the invoice state at print time so later invoice updates
    do not affect the rendered document.
    """

    student = models.ForeignKey("people.Student", on_delete=models.PROTECT)
    semester = models.ForeignKey(
        "timetable.Semester",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    created_by = models.ForeignKey(
        "people.Staff",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    def __str__(self) -> str:  # pragma: no cover
        """Return a short snapshot label for admin lists."""
        semester = self.semester or "All semesters"
        return f"Invoice snapshot {self.pk} - {self.student} ({semester})"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Invoice snapshot"
        verbose_name_plural = "Invoice snapshots"
