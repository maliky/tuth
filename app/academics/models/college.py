from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from app.people.models import FacultyProfile
from typing import Optional, cast

from app.shared.constants import COLLEGE_CHOICES


class College(models.Model):
    """Institutional unit responsible for a set of programmes."""

    code = models.CharField(max_length=4, unique=True)
    fullname = models.CharField(max_length=255)

    def clean(self) -> None:
        if (self.code, self.fullname) not in COLLEGE_CHOICES:
            raise ValidationError("Invalid (code, fullname) pair for College.")

    @property
    def current_dean(self) -> Optional[FacultyProfile]:
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
            return cast(Optional[FacultyProfile], getattr(ra, "facultyprofile", None))
        except FacultyProfile.DoesNotExist:
            return None

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code} - {self.fullname}"
