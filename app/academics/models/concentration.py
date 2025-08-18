"""Concentration module that is Minor and Major."""

from __future__ import annotations

from typing import Self, cast

from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from app.academics.models.curriculum import Curriculum
from app.academics.models.course import CurriculumCourse


class ConcentrationMixin(models.Model):
    """Optional specialization that further narrows a curriculum.

    It generalized and Should be inherited by Major and Minor.
    """

    # to be overrided
    RELATED_NAME: str = "concentration"  # no plural
    DEFAULT_CH: int = 40

    # ~~~~~~~~ Mandatory ~~~~~~~~
    name = models.CharField(max_length=60, unique=True)
    curriculum = models.ForeignKey("academics.Curriculum", on_delete=models.CASCADE)

    # ~~~~~~~~ Optional ~~~~~~~~
    description = models.TextField(blank=True)
    max_credit_hours = models.PositiveIntegerField(
        default=DEFAULT_CH,
        blank=True,
    )

    def __str__(self) -> str:  # pragma: no cover
        """Return the name and associated curriculum."""
        return f"{self.name} ({self.curriculum})"

    def _ensure_saved(self):
        """Make sure the model if saved."""
        if not self.pk:
            self.save()

    def clean(self):
        """Check that at least one curriculum_course exists."""
        super().clean()
        if self.pk and not self.curriculum_courses.exists():  # type: ignore[attr-defined]
            raise ValidationError(
                f"{self.RELATED_NAME} must reference at least one curriculum_course."
            )
        if self.exceeds_credit_limit():
            raise ValidationError(
                f"Total credit hours ({self.total_credit_hours()}) exceed the total "
                f"allowed ({self.max_credit_hours})"
            )

    def total_credit_hours(self) -> int:
        """Return the sum of credit hours for every curriculum_course attached to this concentration."""
        # will return 0 if the object is not saved.
        self._ensure_saved()
        return self.curriculum_courses.aggregate(total=models.Sum("credit_hours")).get("total") or 0  # type: ignore[attr-defined]

    def exceeds_credit_limit(self):
        """True if the total credit hours >  max_credit_hours."""
        return self.total_credit_hours() > self.max_credit_hours

    @classmethod
    def get_default(cls) -> Self:
        """Return a default concentration (Major or Minor) with one curriculum_course."""
        dft_concentration, _ = cls.objects.get_or_create(  # type: ignore[attr-defined]
            name=f"DFT {cls.RELATED_NAME}",
            curriculum=Curriculum.get_default(),
            description=f"This is a default {cls.RELATED_NAME}",
        )
        pg = CurriculumCourse.get_default()
        dft_concentration.curriculum_courses.add(pg)
        dft_concentration.save()  # ? is the save necessary

        return cast(Self, dft_concentration)

    class Meta:
        abstract = True


class Major(ConcentrationMixin):
    """Represent a group of courses of the curriculum making the major."""

    RELATED_NAME: str = "major"

    curriculum_courses = models.ManyToManyField(
        "academics.CurriculumCourse",
        through="academics.MajorCurriculumCourse",
        related_name="majors",
    )
    max_credit_hours = models.PositiveIntegerField(default=50)


class Minor(ConcentrationMixin):
    """Represent a group of courses of the curriculum making the major."""

    RELATED_NAME: str = "minor"
    curriculum_courses = models.ManyToManyField(
        "academics.CurriculumCourse",
        through="academics.MinorCurriculumCourse",
        related_name="minors",
    )
    max_credit_hours = models.PositiveIntegerField(default=20)


# ##  TODO make sure Minor curriculum_course can be in several curriculms?
class MajorCurriculumCourse(models.Model):
    """A table joining the Major table with the curriculum_course table."""

    # ~~~~~~~~ Mandatory ~~~~~~~~
    major = models.ForeignKey("Major", on_delete=models.CASCADE)
    curriculum_course = models.ForeignKey("CurriculumCourse", on_delete=models.CASCADE)
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["major", "curriculum_course"],
                name="uniq_curriculum_course_per_major",
            ),
        ]


class MinorCurriculumCourse(models.Model):
    """A table joining the Major table with the curriculum_course table."""

    # ~~~~~~~~ Mandatory ~~~~~~~~
    minor = models.ForeignKey("Minor", on_delete=models.CASCADE)
    curriculum_course = models.ForeignKey("CurriculumCourse", on_delete=models.CASCADE)
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["minor", "curriculum_course"],
                name="uniq_curriculum_course_per_minor",
            ),
        ]
