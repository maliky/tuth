"""Department model."""

from __future__ import annotations

from django.db import models


class Department(models.Model):
    """Academic department belonging to a college.

    Example:
        >>> from app.academics.models import Department, College
        >>> coas = College.objects.create(code="COAS", long_name="College of Arts and Sciences")
        >>> Department.objects.create(code="MATH", college=coas)
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
        constraints = [
            models.UniqueConstraint(
                fields=["code", "college"],
                name="uniq_department_code_per_college",
            ),
        ]
