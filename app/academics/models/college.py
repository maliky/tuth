"""College module."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from app.shared.constants.academics import CollegeCodeChoices, CollegeLongNameChoices


class College(models.Model):
    """Institutional unit responsible for a set of programmes."""

    # there should be no constraint here as the VPA may need to
    # rework the name of the colleges from time to time.
    code = models.CharField(
        max_length=4,
        choices=CollegeCodeChoices.choices,
        default=CollegeCodeChoices.COAS,
    )

    long_name = models.CharField(
        max_length=50,
        choices=CollegeLongNameChoices.choices,
    )

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code}"

    def clean(self) -> None:
        if self.code and self.long_name:
            if self.code != self.long_name:
                raise ValidationError(
                    f"College code {self.code} and long name {self.long_name} must have the same key."
                )

    def save(self, *args, **kwargs) -> None:
        self.long_name = CollegeLongNameChoices[self.code]
        super().save(*args, **kwargs)
