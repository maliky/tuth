"""Lookup tables for different status."""

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
    """Map numeric credit hour codes to labels."""

    objects = CreditHourManager()

    code = models.PositiveSmallIntegerField(primary_key=True)
    label = models.CharField(max_length=60)

    def __str__(self) -> str:
        """Return human readable label."""
        return self.label

    # class CREDIT_NUMBER(IntegerChoices):
    # ZERO = 0, "0"
    # ONE = 1, "1"
    # TWO = 2, "2"
    # THREE = 3, "3"
    # FOUR = 4, "4"
    # FIVE = 5, "5"
    # SIX = 6, "6"
    # SEVEN = 7, "7"
    # EIGHT = 8, "8"
    # NINE = 9, "9"
    # TEN = 10, "10"
    # TBA = 99, "99"  # to be attributed
