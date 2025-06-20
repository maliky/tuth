"""Department model."""

from __future__ import annotations

from app.academics.models.college import College
from django.db import models


class Department(models.Model):
    """Academic department belonging to a college.

    Example: see get_default()
    """

    code = models.CharField(max_length=50, unique=True, editable=False)
    short_name = models.CharField(max_length=6)
    full_name = models.CharField(max_length=128, blank=True)
    college = models.ForeignKey(
        "academics.College",
        on_delete=models.PROTECT,
        related_name="departments",
    )

    def __str__(self) -> str:  # pragma: no cover
        """The Department common represenation. ! This is not unique."""
        return self.code

    def _get_n_set_code(self) -> str:
        """Builds a unique deparment code from short_name and college."""
        if not self.code:
            self.code = f"{self.college}-{self.short_name}"
        return self.code

    def save(self, *args, **kwargs) -> None:
        """Save the Department making sure the code is set."""
        self._get_n_set_code()
        super().save(*args, **kwargs)

    @classmethod
    def get_default(cls):
        """Return the default Department."""
        default_dept, _ = cls.objects.get_or_create(
            code="DFT",
            full_name="Mathematics' Default Department",
            college=College.get_default(),
        )
        return default_dept

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["short_name", "college"],
                name="uniq_department_code_per_college",
            ),
        ]
