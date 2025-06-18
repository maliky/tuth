"""Concentration module."""

from __future__ import annotations

from django.db import models


class Concentration(models.Model):
    """Optional specialization that further narrows a curriculum.

    Example:
        >>> Concentration.objects.create(name="Agro", curriculum=curriculum)
    """

    # revoir
    name = models.CharField(max_length=255)
    curriculum = models.ForeignKey(
        "academics.curriculum",
        on_delete=models.CASCADE,
        related_name="concentrations",
    )

    # courses = models.ManyToManyField(
    #     "academics.Course",
    #     related_name="curricula",  # <-- reverse accessor course.curricula
    #     blank=True,
    # )

    def __str__(self) -> str:  # pragma: no cover
        """Return the name and associated curriculum."""
        return f"{self.name} ({self.curriculum})"
