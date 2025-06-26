"""Curriculum module."""

from __future__ import annotations
from datetime import date

from app.academics.choices import StatusCurriculum
from app.academics.models.college import College
from django.db import models

from app.shared.status.mixins import StatusableMixin


class Curriculum(StatusableMixin, models.Model):
    """Set of courses that make up a degree programme within a college.

    Example:
        >>> col = College.objects.create(code="COAS", long_name="Arts and Sciences")
        >>> Curriculum.objects.create(short_name="BSCS", college=col)

    We use a default curriculm incompassing all the courses for non specified
    curriculum, otherwize the student should be limited to the courses listed
    in their curriculum.
    """

    short_name = models.CharField(max_length=40)
    long_name = models.CharField(max_length=255, blank=True, null=True)

    college = models.ForeignKey(
        "academics.College", on_delete=models.CASCADE, related_name="curricula"
    )
    courses = models.ManyToManyField(
        "academics.Course",
        through="academics.Program",
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

    @classmethod
    def get_default(cls) -> Curriculum:
        """Returns a default curriculum."""
        def_curriculum, _ = cls.objects.get_or_create(
            short_name="DFT_CUR",
            long_name="Default Curriculum",
            college=College.get_default(),
        )
        return def_curriculum

    def save(self, *args, **kwargs):
        """Save a curriculum instance while setting defaults."""
        if not self.college:
            self.college = College.get_default()
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
