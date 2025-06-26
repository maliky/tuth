"""Space module."""

from __future__ import annotations

from itertools import count

from django.db import models

# Reside only on module reload (so could stay in memory for long on prod)
DEFAULT_ROOM_CODE = count(start=1, step=1)


class Space(models.Model):
    """Physical structure that groups multiple rooms.

    Example:
        >>> from app.spaces.models.core import Space
        >>> Space.objects.create(code="AA", full_name="Academic Annex")
    """

    code = models.CharField(max_length=15, unique=True, db_index=True)
    full_name = models.CharField(max_length=128, blank=True)

    def __str__(self) -> str:  # pragma: no cover
        return self.code

    @classmethod
    def get_default(cls):
        """Returns a TBA instance of the Space."""
        tba_space, _ = cls.objects.get_or_create(
            code="TBA", defaults={"full_name": "Undefined space (TBA)"}
        )
        return tba_space

    class Meta:
        verbose_name = "Space / Buiding"
        verbose_name_plural = "Spaces / Buildings"


class Room(models.Model):
    """Individual teaching space located in a space.

    Example:
        >>> from app.spaces.models.core import Room
        >>> Room.objects.create(code="101", space=space)
    """

    code = models.CharField(max_length=30)
    space = models.ForeignKey(Space, on_delete=models.PROTECT, related_name="rooms")

    standard_capacity = models.PositiveIntegerField(default=45)
    exam_capacity = models.PositiveIntegerField(default=30)

    def __str__(self) -> str:  # pragma: no cover
        """Full room identifier combining space short name and code."""
        if self.space_id:
            return f"{self.space}-{self.code}"
        else:
            return f"{self.code} (Space)"

    def _ensure_code(self):
        if not self.code:
            self.code = "TBA"

    def _ensure_space(self):
        if not self.space_id:
            self.space = Space.get_default()

    def save(self, *args, **kwargs):
        """Make sure we have a room even if it's TBA."""
        self._ensure_code()
        self._ensure_space()
        super().save(*args, **kwargs)

    @classmethod
    def get_default(cls, code: int = 0):
        """Returns a default Room."""
        dft_room, _ = cls.objects.get_or_create(
            code=f"TBA{code:04d}", space=Space.get_default()
        )
        return dft_room

    @classmethod
    def get_unique_default(cls):
        """Returns a default unique Room."""
        return Room.get_default(code=next(DEFAULT_ROOM_CODE))

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
