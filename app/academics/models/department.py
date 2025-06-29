"""Department model."""

from __future__ import annotations
from typing import Self

from app.academics.models.college import College
from django.db import models


class Department(models.Model):
    """Academic department belonging to a college.

    Example: see get_default()
    """

    # mandatory
    short_name = models.CharField(max_length=6)
    # woulde be good to restric this to a few dept.
    # but it is also here that I should set the Truth
    # short_name = models.CharField(
    #     max_length=6,
    #     choices=DepartmentShortNameChoice.choices,
    #     default=DepartmentShortNameChoice.DEFT,
    # )

    # Auto-completed
    college = models.ForeignKey(
        "academics.College",
        on_delete=models.PROTECT,
        related_name="departments",
    )
    long_name = models.CharField(max_length=128, blank=True)

    # non editable
    code = models.CharField(max_length=50, unique=True, editable=False)

    def __str__(self) -> str:  # pragma: no cover
        """The Department common representaion. ! This is not unique."""
        return self.code

    def _ensure_code(self) -> None:
        """Build a unique department code from short_name and college."""
        if not self.code:
            self.code = f"{self.college}-{self.short_name}"

    def _ensure_college(self) -> None:
        """Make sure to have a college for the department."""
        if not self.college_id:
            self.college = College.get_default()

    def _ensure_long_name(self) -> None:
        """Make sure a title is set."""
        if not self.long_name:
            self.long_name = f"{self.code} Department in {self.college}"

    def save(self, *args, **kwargs) -> None:
        """Save the Department making sure the code is set."""
        self._ensure_code()
        self._ensure_college()
        self._ensure_long_name()
        super().save(*args, **kwargs)

    @classmethod
    def get_default(cls, short_name="DFT") -> Self:
        """Return the default Department."""
        default_dept, _ = cls.objects.get_or_create(
            short_name=short_name,
            long_name=f"Department of {short_name}",
            college=College.get_default(),
        )
        return default_dept

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["short_name", "college"],
                name="uniq_department_short_name_per_college",
            ),
        ]
