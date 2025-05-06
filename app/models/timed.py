from __future__ import annotations

from django.db import models
from django.core.validators import MinValueValidator
from django.db.models.functions import ExtractYear
from django.core.exceptions import ValidationError

from app.models.academics import Course  # avoid circular import
from app.models.spaces import Room


# ------------------------------------------------------------------
# Academic Year & Term
# ------------------------------------------------------------------


class AcademicYear(models.Model):
    starting_date = models.DateField(unique=True)
    long_name = models.CharField(max_length=9, editable=False, unique=True)
    short_name = models.CharField(max_length=5, editable=False, unique=True)

    def clean(self) -> None:
        if self.starting_date.month not in (7, 8, 9, 10):
            raise ValidationError("Start date must be in July–October.")

    def save(self, *args, **kwargs) -> None:
        ys = self.starting_date.year
        ye = ys + 1
        self.long_name = f"{ys}/{ye}"
        self.short_name = f"{str(ys)[-2:]}-{str(ye)[-2:]}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover
        return self.long_name

    class Meta:
        constraints = [
            models.UniqueConstraint(
                ExtractYear("starting_date"),
                name="uniq_academic_year_by_year",
            )
        ]
        ordering = ["-starting_date"]


class Term(models.Model):
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="terms"
    )
    number = models.PositiveSmallIntegerField(
        choices=[(1, "1"), (2, "2"), (3, "3")],
        help_text="1, 2 or 3 (first, second or summer semester).",
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "number"], name="uniq_term_per_year"
            )
        ]
        ordering = ["academic_year__starting_date", "number"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.academic_year.short_name}_T{self.number}"


# ------------------------------------------------------------------
# Section
# ------------------------------------------------------------------


class Section(models.Model):
    course = models.ForeignKey(Course, related_name="sections", on_delete=models.PROTECT)
    number = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    term = models.ForeignKey(Term, on_delete=models.PROTECT)
    instructor = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        limit_choices_to={"role_assignments__role": "Instructor"},
        on_delete=models.SET_NULL,
    )
    # could try lasy reference
    room = models.ForeignKey(Room, null=True, blank=True, on_delete=models.SET_NULL)
    schedule = models.CharField(max_length=100, blank=True)
    max_seats = models.PositiveIntegerField(default=30, validators=[MinValueValidator(3)])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course", "term", "number"],
                name="uniq_section_per_course_term",
            )
        ]
        ordering = ["term__academic_year__starting_date", "term__number", "course__name"]

    # ---------- display helpers ----------
    @property
    def short_code(self) -> str:
        return f"{self.course.code}:s{self.number}"

    @property
    def long_code(self) -> str:
        return (
            f"{self.term.academic_year.short_name}_T{self.term.number} {self.short_code}"
        )

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.short_code} | {self.term} | {self.room}"
