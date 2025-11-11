"""Department model."""
from __future__ import annotations

from typing import Self, cast

from django.db import models
from simple_history.models import HistoricalRecords

from app.academics.models.college import College


class Department(models.Model):
    """Academic department belonging to a college.

    Example: see get_default()
    """
    # ~~~~~~~~ Mandatory ~~~~~~~~
    short_name = models.CharField(max_length=8)
    # would be good to restric this to a few dept.
    # but it is also here that I should set the Truth
    # short_name = models.CharField(
    #     max_length=6,
    #     choices=DepartmentShortNameChoice.choices,
    #     default=DepartmentShortNameChoice.DEFT,
    # )

    # ~~~~ Auto-filled ~~~~
    college = models.ForeignKey(
        "academics.College",
        on_delete=models.PROTECT,
        related_name="departments",
    )
    long_name = models.CharField(max_length=128, blank=True)
    history = HistoricalRecords()

    # ~~~~ Read-only ~~~~
    code = models.CharField(max_length=50, unique=True, editable=False)

    def __str__(self) -> str:  # pragma: no cover
        """The Department common representation. ! This is not unique."""
        return f"({self.college.code}) {self.short_name}"

    def _ensure_code(self) -> None:
        """Build a unique department code from short_name and college."""
        if not self.code:
            self.code = f"{self.college.code}-{self.short_name}"

    def _ensure_college(self) -> None:
        """Make sure to have a college for the department."""
        if not self.college_id:
            self.college = College.get_default()

    def _ensure_long_name(self) -> None:
        """Make sure a title is set."""
        if not self.long_name:
            self.long_name = f"{self.short_name} department of {self.college}"

    def get_courses(self) -> models.QuerySet:
        """Return all the courses for this department."""
        return self.courses.all().order_by("number")

    def course_count(self) -> int:
        """Count the number of courses for this department."""
        return self.courses.count()

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
        return cast(Self, default_dept)

    class Meta:
        ordering = ["college__code", "short_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["short_name", "college"],
                name="uniq_department_short_name_per_college",
            ),
        ]
