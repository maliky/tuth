"""College module."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from app.academics.choices import CollegeCodeChoices, CollegeLongNameChoices


class College(models.Model):
    """Institutional unit responsible for a set of programmes.

    Example: See get_default

    Side Effects:
        save() sets long_name based on code.
    """

    # ! there should be no constraint here as the VPA may need to
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

    @classmethod
    def get_default(cls):
        """Return the default college."""
        # will set the long_name by default on save
        def_clg, _ = cls.get_or_create(code=CollegeCodeChoices.COAS)
        return def_clg

    def clean(self) -> None:
        """Validate that code and long_name refer to the same entry."""
        if self.code and self.long_name:
            if self.code != self.long_name:
                raise ValidationError(
                    f"College code {self.code} and long name {self.long_name} must have the same key."
                )

    def save(self, *args, **kwargs) -> None:
        """Ensure long_name matches the selected code before saving."""
        if self.long_name is None:
            self.long_name = CollegeLongNameChoices[self.code]
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["code"]
