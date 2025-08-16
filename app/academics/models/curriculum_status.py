"""Lookup model for curriculum validation statuses."""

from django.db import models


class CurriculumStatus(models.Model):
    """Code/label pairs for curriculum validation status."""

    code = models.CharField(max_length=30, primary_key=True)
    label = models.CharField(max_length=60)

    def __str__(self) -> str:  # pragma: no cover - simple display
        """Return the human label."""
        return self.label

    class Meta:
        ordering = ["code"]
