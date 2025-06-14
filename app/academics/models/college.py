"""College module."""

from __future__ import annotations

from typing import Optional, cast

from django.core.exceptions import ValidationError
from django.db import models

from app.people.models import Faculty
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

    @property
    def current_dean(self) -> Optional[Faculty]:
        """Return the user currently assigned as dean or ``None``."""

        ra = (
            self.role_assignments.filter(role="Dean", end_date__isnull=True)
            .order_by("-start_date")
            .select_related("user")
            .first()
        )
        if not ra:
            return None
        try:
            return cast(Optional[Faculty], getattr(ra, "facultyprofile", None))
        except Faculty.DoesNotExist:
            return None

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code}"

    def clean(self) -> None:
        """Validate that ``code`` and ``long_name`` refer to the same entry."""
        if self.code and self.long_name:
            if self.code != self.long_name:
                raise ValidationError(
                    f"College code {self.code} and long name {self.long_name} must have the same key."
                )

    def save(self, *args, **kwargs):
        """Ensure ``long_name`` matches the selected ``code`` before saving."""
        self.long_name = CollegeLongNameChoices[self.code]
        super().save(*args, **kwargs)
