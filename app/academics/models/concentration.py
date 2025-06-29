"""Concentration module."""

from __future__ import annotations
from typing import Self

from app.academics.models.curriculum import Curriculum
from django.db import models


class Concentration(models.Model):
    """Optional specialization that further narrows a curriculum.

    Example:
        >>> curriculum = Curriculum.objects.first()
        >>> Concentration.objects.create(name="Statistics", curriculum=curriculum)
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

    @classmethod
    def get_default(cls) -> Self:
        """Return a default concentration."""
        dft_concentration, _ = cls.objects.get_or_create(
            name="Default Concentration", curriculum=Curriculum.get_default()
        )
        return dft_concentration
