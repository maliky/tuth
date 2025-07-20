"""Concentration module that is Minor and Major."""

from __future__ import annotations

from typing import Self, cast

from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from app.academics.models.curriculum import Curriculum
from app.academics.models.program import Program


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
        """Check that at least one program exists."""
        super().clean()
        if self.pk and not self.programs.exists():  # type: ignore[attr-defined]
            raise ValidationError(
                f"{self.RELATED_NAME} must reference at least one program."
            )
        if self.exceeds_credit_limit():
            raise ValidationError(
                f"Total credit hours ({self.total_credit_hours()}) exceed the total "
                f"allowed ({self.max_credit_hours})"
            )

    def total_credit_hours(self) -> int:
        """Return the sum of credit hours for every program attached to this concentration."""
        # will return 0 if the object is not saved.
        self._ensure_saved()
        return self.programs.aggregate(total=models.Sum("credit_hours")).get("total") or 0  # type: ignore[attr-defined]

    def exceeds_credit_limit(self):
        """True if the total credit hours >  max_credit_hours."""
        return self.total_credit_hours() > self.max_credit_hours

    @classmethod
    def get_default(cls) -> Self:
        """Return a default concentration (Major or Minor) with one program."""
        dft_concentration, _ = cls.objects.get_or_create(  # type: ignore[attr-defined]
            name=f"DFT {cls.RELATED_NAME}",
            curriculum=Curriculum.get_default(),
            description=f"This is a default {cls.RELATED_NAME}",
        )
        pg = Program.get_default()
        dft_concentration.programs.add(pg)
        dft_concentration.save()  # ? is the save necessary

        return cast(Self, dft_concentration)

    class Meta:
        abstract = True


class Major(ConcentrationMixin):
    """Represent a group of courses of the curriculum making the major."""

    RELATED_NAME: str = "major"

    programs = models.ManyToManyField(
        "academics.Program", through="academics.MajorProgram", related_name="majors"
    )
    max_credit_hours = models.PositiveIntegerField(default=50)


class Minor(ConcentrationMixin):
    """Represent a group of courses of the curriculum making the major."""

    RELATED_NAME: str = "minor"
    programs = models.ManyToManyField(
        "academics.Program", through="academics.MinorProgram", related_name="minors"
    )
    max_credit_hours = models.PositiveIntegerField(default=20)


# ##  TODO make sure Minor program can be in several curriculms?
class MajorProgram(models.Model):
    """A table joining the Major table with the program table."""

    # ~~~~~~~~ Mandatory ~~~~~~~~
    major = models.ForeignKey("Major", on_delete=models.CASCADE)
    program = models.ForeignKey("Program", on_delete=models.CASCADE)
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["major", "program"],
                name="uniq_program_per_major",
            ),
        ]


class MinorProgram(models.Model):
    """A table joining the Major table with the program table."""

    # ~~~~~~~~ Mandatory ~~~~~~~~
    minor = models.ForeignKey("Minor", on_delete=models.CASCADE)
    program = models.ForeignKey("Program", on_delete=models.CASCADE)
    # ~~~~ Auto-filled ~~~~
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["minor", "program"],
                name="uniq_program_per_minor",
            ),
        ]
