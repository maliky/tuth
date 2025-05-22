from __future__ import annotations

from django.db import models

from app.spaces.models import Building


class Room(models.Model):
    name = models.CharField(max_length=30)
    building = models.ForeignKey(
        Building, null=True, blank=True, on_delete=models.SET_NULL, related_name="rooms"
    )
    standard_capacity = models.PositiveIntegerField(default=45)
    exam_capacity = models.PositiveIntegerField(default=30)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "building"], name="unique_room_per_building"
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        if self.building:
            return f"{self.building} {self.name}"
        return self.name
