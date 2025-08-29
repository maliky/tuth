"""Lookup tables for different status."""

from typing import Self
from django.db import models
from django.core.exceptions import ObjectDoesNotExist


class CreditHourManager(models.Manager):
    """Automatically create credit hours on demand."""

    def get(self, *args, **kwargs):  # type: ignore[override]
        """Return existing credit hour or create it if missing."""
        try:
            return super().get(*args, **kwargs)
        except ObjectDoesNotExist:
            code = kwargs.get("code")
            if code is None:
                raise
            # Use the numeric code as the human-readable label
            return super().create(code=code, label=str(code))


class CreditHour(models.Model):
    """Map numeric credit hour codes to labels.

    The idea is to controle the type of credit a course can have.
    """

    class Meta:
        ordering = ["code"]

    DEFAULT_VALUES: list[tuple[int, str]] = [
        (0, "0"),
        (1, "1"),
        (2, "2"),
        (3, "3"),
        (4, "4"),
        (5, "5"),
        (6, "6"),
        (7, "7"),
        (8, "8"),
        (9, "9"),
        (10, "10"),
        (99, "99"),
    ]

    objects = CreditHourManager()

    code = models.PositiveSmallIntegerField(primary_key=True)
    label = models.CharField(max_length=60)

    @classmethod
    def _populate_attributes_and_db(cls):
        """Create a row for each var in DEFAULT_VALUES and create subclass attributes."""
        # This method is temporary
        for val, lbl in cls.DEFAULT_VALUES:
            obj, _ = cls.objects.get_or_create(code=val, defaults={"label": lbl})

    @classmethod
    def get_default(cls) -> Self:
        """Return the default credit hours."""

        def_ch, _ = cls.objects.get_or_create(code=3)
        return def_ch

    def __str__(self) -> str:
        """Return human readable label."""
        return self.label
