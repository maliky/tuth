"""Building module."""

from __future__ import annotations

from django.db import models


class Building(models.Model):
    """Physical structure that groups multiple rooms."""

    short_name = models.CharField(max_length=10, unique=True)
    full_name = models.CharField(max_length=100, blank=True)

    def __str__(self) -> str:  # pragma: no cover
        return self.short_name
