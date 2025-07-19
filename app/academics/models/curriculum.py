"""Curriculum module."""

from __future__ import annotations

from datetime import date
from typing import Self

from django.db import models
from simple_history.models import HistoricalRecords

from app.academics.choices import StatusCurriculum
from app.academics.models.college import College
from app.shared.status.mixins import StatusableMixin


class Curriculum(StatusableMixin, models.Model):
    """Set of courses that make up a degree programme within a college.

    Example:
        >>> col = College.objects.create(code="COAS", long_name="Arts and Sciences")
        >>> Curriculum.objects.create(short_name="BSCS", college=col)

    We use a default curriculum encompassing all courses when none is specified;
    otherwise the student is limited to the courses listed in their curriculum.

    Concerning credit hours, usualy between 120-128 (GE 30-40, Major/Specific 30-60, Minor/elective (rest))
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    short_name = models.CharField(max_length=40)

    # ~~~~ Auto-filled ~~~~
    college = models.ForeignKey(
        "academics.College", on_delete=models.CASCADE, related_name="curricula"
    )
    creation_date = models.DateField(default=date.today)
    is_active = models.BooleanField(default=False)
    status = models.CharField(
        max_length=30,
        choices=StatusCurriculum.choices,
        default=StatusCurriculum.PENDING,
    )
    history = HistoricalRecords()

    # ~~~~~~~~ Optional ~~~~~~~~
    long_name = models.CharField(max_length=255, blank=True, null=True)
    courses = models.ManyToManyField(
        "academics.Course",
        through="academics.Program",
        related_name="curricula",  # <-- reverse accessor course.curricula
        blank=True,
    )

    def __str__(self) -> str:  # pragma: no cover
        """Return the college (if set): & curriculum short name."""
        _prefix = f" ({self.college})" if self.college_id else ""
        return self.short_name + _prefix

    @classmethod
    def get_default(cls, short_name="DFT_CUR") -> Self:
        """Returns a default curriculum."""
        def_curriculum, _ = cls.objects.get_or_create(
            short_name=short_name,
            long_name="Default Curriculum",
            college=College.get_default(),
        )
        return def_curriculum

    def _ensure_activity(self):
        """Make sure than only an aproved curriculum can be active."""
        # > TODO would be good to bubble up a warning message to inform user
        # of the change.
        if self.status != StatusCurriculum.APPROVED:
            self.is_active = False

    def save(self, *args, **kwargs):
        """Save a curriculum instance while setting defaults."""
        if not self.college_id:
            self.college = College.get_default()
        self._ensure_activity()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        """Validate the curriculum and its current status."""
        super().clean()
        self.validate_status(StatusCurriculum)

    class Meta:
        ordering = ["college", "short_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["college", "short_name"],
                condition=models.Q(is_active=True),
                name="uniq_active_curriculum_college",
            )
        ]
