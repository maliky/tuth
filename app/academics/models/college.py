"""College module."""

from __future__ import annotations

from django.db import models
from simple_history.models import HistoricalRecords

from app.academics.choices import CollegeCodeChoices, CollegeLongNameChoices


class College(models.Model):
    """Institutional unit responsible for a set of programmes.

    Example: See get_default

    Side Effects:
        save() sets long_name based on code.
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    code = models.CharField(
        max_length=4,
        choices=CollegeCodeChoices.choices,
        default=CollegeCodeChoices.COAS,
    )

    # ~~~~ Auto-filled ~~~~
    long_name = models.CharField(
        max_length=50,
        # choices=CollegeLongNameChoices.choices,
        blank=True,
    )
    history = HistoricalRecords()
    
    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code}"

    # > TODO get some properties to list the number of unique enrolled students per
    # level freshman, sophomore, junior, senior
    # the name of the departments (with name of chairs)
    # the name of the curriculum
    # the number of faculties
    # the number of unique courses offered by that college.

    @classmethod
    def get_default(cls) -> College:
        """Return the default college ie. COAS."""
        # will set the long_name by default on save
        def_clg, _ = cls.objects.get_or_create(code=CollegeCodeChoices.DEFT)
        return def_clg

    def _ensure_long_name(self) -> None:
        """Set the long name base on the college code if none where provided."""
        if not self.long_name:
            self.long_name = CollegeLongNameChoices[self.code.upper()].label

    def save(self, *args, **kwargs) -> None:
        """Ensure long_name matches the selected code before saving."""
        self._ensure_long_name()
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["code"], name="unique_college_code"),
            models.UniqueConstraint(fields=["long_name"], name="unique_college_name"),
        ]
        ordering = ["code"]
