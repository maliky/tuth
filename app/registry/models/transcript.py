"""Transcript request tracking for the Registrar dashboard."""

from __future__ import annotations

from django.db import models

from app.shared.mixins import SimpleTableMixin
from app.shared.status.mixins import StatusableMixin


class TranscriptRequestStatus(SimpleTableMixin):
    """Lookup table storing allowed states for transcript requests."""

    DEFAULT_VALUES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("on_hold", "On hold"),
    ]

    @classmethod
    def get_default(cls):
        """Return the default status."""
        default, _ = cls.objects.get_or_create(code="pending", defaults={"label": "Pending"})
        return default


class TranscriptRequest(StatusableMixin, models.Model):
    """Records a student's transcript request and its fulfillment status."""

    DELIVERY_CHOICES = [
        ("pickup", "Pick up at registrar"),
        ("email", "Email"),
        ("courier", "Courier / postal service"),
    ]

    student = models.ForeignKey(
        "people.Student",
        on_delete=models.CASCADE,
        related_name="transcript_requests",
    )
    status = models.ForeignKey(
        "registry.TranscriptRequestStatus",
        on_delete=models.PROTECT,
        related_name="requests",
    )
    destination_name = models.CharField(max_length=255)
    destination_email = models.EmailField(blank=True)
    destination_address = models.TextField(blank=True)
    purpose = models.CharField(max_length=120, blank=True)
    delivery_method = models.CharField(
        max_length=20, choices=DELIVERY_CHOICES, default="pickup"
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.student} → {self.destination_name} ({self.status})"

    def save(self, *args, **kwargs):
        """Ensure a default status exists before saving."""
        if not self.status_id:
            self.status = TranscriptRequestStatus.get_default()
        return super().save(*args, **kwargs)
