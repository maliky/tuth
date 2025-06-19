"""Curriculum module."""

from __future__ import annotations
from datetime import date

from app.shared.constants.academics import StatusCurriculum
from django.db import models

from app.shared.status.mixins import StatusableMixin


class Curriculum(StatusableMixin, models.Model):
    """Set of courses that make up a degree programme within a college.

    Example:
        >>> from app.academics.models import Curriculum, College
        >>> col = College.objects.create(code="COAS", long_name="Arts and Sciences")
        >>> Curriculum.objects.create(short_name="BSCS", college=col)

    Side Effects:
        Status changes update ``is_active`` via signals.
    """

    short_name = models.CharField(max_length=40)
    long_name = models.CharField(max_length=255, blank=True, null=True)

    college = models.ForeignKey(
        "academics.College", on_delete=models.CASCADE, related_name="curricula"
    )
    courses = models.ManyToManyField(
        "academics.Course",
        through="academics.CurriculumCourse",
        related_name="curricula",  # <-- reverse accessor course.curricula
        blank=True,
    )
    # a constraint is that we should not have a curriculum in a college
    # created in the same year with same title
    creation_date = models.DateField(default=date.today)
    is_active = models.BooleanField(default=False)

    status = models.CharField(
        max_length=30,
        choices=StatusCurriculum.choices,
        default=StatusCurriculum.PENDING,
    )

    def __str__(self) -> str:  # pragma: no cover
        """Return the curriculum short name."""
        return f"{self.college}: {self.short_name}"

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
