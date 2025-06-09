"""Space module."""

from __future__ import annotations

from django.db import models


class Space(models.Model):
    """Physical structure that groups multiple rooms."""

    code = models.CharField(max_length=15, unique=True, db_index=True)
    full_name = models.CharField(max_length=128, blank=True)

    def __str__(self) -> str:  # pragma: no cover
        return self.code


class Room(models.Model):
    """Individual teaching space located in a space."""

    code = models.CharField(max_length=30)
    space = models.ForeignKey(
        Space, null=True, blank=True, on_delete=models.PROTECT, related_name="rooms"
    )

    standard_capacity = models.PositiveIntegerField(default=45)
    exam_capacity = models.PositiveIntegerField(default=30)

    @property
    def full_code(self) -> str:
        """Full room identifier combining space short name and code."""
        return f"{self.space}-{self.code}"

    def __str__(self) -> str:  # pragma: no cover
        return self.code

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["space", "code"], name="unique_room_per_space"
            )
        ]
        indexes = [
            models.Index(fields=["space", "code"]),
        ]
        ordering = ["space__short_name", "code"]
