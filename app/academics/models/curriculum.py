from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from app.shared.utils import validate_model_status
from app.shared.mixins import StatusableMixin


class Curriculum(StatusableMixin, models.Model):
    """Academic programme offered by a College."""

    short_name = models.CharField(max_length=30)
    title = models.CharField(max_length=255, blank=True, null=True)

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
    creation_date = models.DateField()
    is_active = models.BooleanField(default=False)

    status_history = GenericRelation(
        "shared.StatusHistory", related_query_name="curriculum"
    )

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.title or self.short_name}"

    def clean(self):
        """Validate the curriculum and its current status."""

        super().clean()
        validate_model_status(self)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["college", "title"],
                condition=models.Q(is_active=True),
                name="uniq_active_curriculum_college",
            )
        ]
