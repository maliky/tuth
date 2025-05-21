from __future__ import annotations

from app.constants.choices import SEMESTER_NUMBER, TERM_NUMBER
from django.db import models
from django.core.validators import MinValueValidator
from django.db.models.functions import ExtractYear
from django.core.exceptions import ValidationError
from app.models.utils import validate_subperiod
from datetime import timedelta

# ------------------------------------------------------------------
# Academic Year & Semesters & Term
# ------------------------------------------------------------------


class AcademicYear(models.Model):
    start_date = models.DateField(unique=True)
    end_date = models.DateField(unique=True)
    long_name = models.CharField(max_length=9, editable=False, unique=True)
    short_name = models.CharField(max_length=5, editable=False, unique=True)

    def clean(self) -> None:
        if self.start_date.month not in (7, 8, 9, 10):
            raise ValidationError("Start date must be in July–October.")

    def save(self, *args, **kwargs) -> None:
        ys = self.start_date.year

        if self.start_date and not self.end_date:
            # the day *before* next academic year starts
            self.end_date = self.start_date.replace(year=ys + 1) - timedelta(days=1)

        ye = ys + 1
        self.long_name = f"{ys}/{ye}"
        self.short_name = f"{str(ys)[-2:]}-{str(ye)[-2:]}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover
        return self.long_name

    class Meta:
        constraints = [
            models.UniqueConstraint(
                ExtractYear("start_date"),
                name="uniq_academic_year_by_year",
            )
        ]
        ordering = ["-start_date"]


class Semester(models.Model):
    academic_year = models.ForeignKey(
        "app.AcademicYear", on_delete=models.PROTECT, related_name="semesters"
    )
    number = models.PositiveSmallIntegerField(
        choices=SEMESTER_NUMBER.choices, help_text="Semester number"
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def clean(self) -> None:
        "Checking that the start and end date of the Semester are within the academic years dates"
        # Semester.clean() and Term.clean() call validate_subperiod() but not
        # full_clean() on related objects. In admin workflows the parent may still
        # carry invalid dates. Consider a parent-before-child save order or
        # database-level CHECK constraints.
        validate_subperiod(
            sub_start=self.start_date,
            sub_end=self.end_date,
            container_start=self.academic_year.start_date,
            container_end=self.academic_year.end_date,
            overlap_qs=Semester.objects.filter(academic_year=self.academic_year).exclude(
                pk=self.pk
            ),
            overlap_message="Overlapping Semesters in the same academic year.",
            label="semester",
        )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "number"], name="uniq_semester_per_year"
            )
        ]
        ordering = ["start_date"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.academic_year.short_name}_Sem{self.number}"


class Term(models.Model):
    semester = models.ForeignKey(
        "app.Semester", on_delete=models.PROTECT, related_name="terms"
    )
    number = models.PositiveSmallIntegerField(
        choices=TERM_NUMBER.choices, help_text="Term number"
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def clean(self):
        validate_subperiod(
            sub_start=self.start_date,
            sub_end=self.end_date,
            container_start=self.semester.start_date,
            container_end=self.semester.end_date,
            overlap_qs=Term.objects.filter(semester=self.semester).exclude(pk=self.pk),
            overlap_message="Overlapping terms in the same semester.",
            label="term",
        )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["semester", "number"], name="uniq_term_per_semester"
            )
        ]
        ordering = ["start_date", "number"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.semester}T{self.number}"


# ------------------------------------------------------------------
# Section
# ------------------------------------------------------------------


class Section(models.Model):
    course = models.ForeignKey(
        "app.Course", related_name="sections", on_delete=models.PROTECT
    )
    number = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    semester = models.ForeignKey(Semester, on_delete=models.PROTECT)
    instructor = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        limit_choices_to={"role_assignments__role": "Instructor"},
        on_delete=models.SET_NULL,
    )
    # could try lasy reference
    room = models.ForeignKey("app.Room", null=True, blank=True, on_delete=models.SET_NULL)
    schedule = models.CharField(max_length=100, blank=True)
    max_seats = models.PositiveIntegerField(default=30, validators=[MinValueValidator(3)])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course", "semester", "number"],
                name="uniq_section_per_course_semester",
            )
        ]
        ordering = ["semester__academic_year__start_date", "course__name"]

    # ---------- display helpers ----------
    @property
    def short_code(self) -> str:
        return f"{self.course.code}:s{self.number}"

    @property
    def long_code(self) -> str:
        return f"{self.semester} {self.short_code}"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.long_code} | {self.room}"
