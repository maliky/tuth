"""Building module."""

from __future__ import annotations

from django.db import models


class Building(models.Model):
    """Physical structure that groups multiple rooms."""

    short_name = models.CharField(max_length=10, unique=True)
    full_name = models.CharField(max_length=100, blank=True)

    def __str__(self) -> str:  # pragma: no cover
        return self.short_name


class Room(models.Model):
    """Individual teaching space located in a building."""

    building = models.ForeignKey(
        Building, null=True, blank=True, on_delete=models.SET_NULL, related_name="rooms"
    )
    code = models.CharField(max_length=30)
    standard_capacity = models.PositiveIntegerField(default=45)
    exam_capacity = models.PositiveIntegerField(default=30)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["code", "building"], name="unique_room_per_building"
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        if self.building:
            return f"{self.building}-{self.code}"
        return self.code
