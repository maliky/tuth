"""Space module."""

from __future__ import annotations

from django.db import models


class Space(models.Model):
    """Physical structure that groups multiple rooms.

    Example:
        >>> from app.spaces.models import Space
        >>> Space.objects.create(code="AA", full_name="Academic Annex")
    """

    code = models.CharField(max_length=15, unique=True, db_index=True)
    full_name = models.CharField(max_length=128, blank=True)

    def __str__(self) -> str:  # pragma: no cover
        return self.code

    @classmethod
    def get_tba_space(cls):
        """Returns a TBA instance of the Space."""
        tba_space, _ = cls.objects.get_or_create(
            code="TBA", defaults={"full_name": "To Be Announced"}
        )
        return tba_space

    class Meta:
        verbose_name = "Space / Buiding"
        verbose_name_plural = "Spaces / Buildings"


class Room(models.Model):
    """Individual teaching space located in a space.

    Example:
        >>> from app.spaces.models import Room
        >>> Room.objects.create(code="101", space=space)
    """

    code = models.CharField(max_length=30)
    space = models.ForeignKey(
        Space, null=True, blank=True, on_delete=models.PROTECT, related_name="rooms"
    )

    standard_capacity = models.PositiveIntegerField(default=45)
    exam_capacity = models.PositiveIntegerField(default=30)

    def __str__(self) -> str:  # pragma: no cover
        return self.full_code

    @property
    def full_code(self) -> str:
        """Full room identifier combining space short name and code."""
        if self.is_specific_room():
            return f"{self.space}-{self.code}"
        else:
            return f"{self.code} (Space)"

    def is_specific_room(self):
        """Returns true if the room is inside a space/buildings which is set."""
        space_str = f"{self.space}".lower()
        code_str = self.code.lower()
        return space_str != code_str

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["space", "code"], name="unique_room_per_space"
            )
        ]
        indexes = [
            models.Index(fields=["space", "code"]),
        ]
        ordering = ["space__code", "code"]
