"""Lookup model for credit hour values."""

from django.db import models


class CreditHour(models.Model):
    """Map numeric credit hour codes to labels."""

    code = models.PositiveSmallIntegerField(primary_key=True)
    label = models.CharField(max_length=10)

    def __str__(self) -> str:  # pragma: no cover - simple display
        """Return the human label."""
        return self.label

    class Meta:
        ordering = ["code"]
