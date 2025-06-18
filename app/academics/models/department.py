"""Department model."""

from __future__ import annotations

from django.db import models


class Department(models.Model):
    """Academic department belonging to a college.

    Example:
        >>> department_factory(code="ENG")
    """

    code = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=128, blank=True)
    college = models.ForeignKey(
        "academics.College",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="departments",
    )

    def __str__(self) -> str:  # pragma: no cover
        return self.code

    class Meta:
        ordering = ["code"]
