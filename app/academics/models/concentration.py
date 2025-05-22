from __future__ import annotations

from django.db import models


class Concentration(models.Model):
    """Optional major for a curriculum."""

    name = models.CharField(max_length=255)
    curriculum = models.ForeignKey(
        "academics.curriculum",
        on_delete=models.CASCADE,
        related_name="concentrations",
    )

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} ({self.curriculum})"
