"""Curriculum course module."""

from __future__ import annotations

from django.db import models

from app.shared.enums import CREDIT_NUMBER, LEVEL_NUMBER, SEMESTER_NUMBER


class CurriculumCourse(models.Model):
    """
    Junction table between Curriculum and Course.
    You can extend it with fields such as `semester_level`,
    `is_required`, `order_in_semester`,
    """

    curriculum = models.ForeignKey(
        "academics.Curriculum", on_delete=models.CASCADE, related_name="programme_lines"
    )
    course = models.ForeignKey(
        "academics.Course", on_delete=models.CASCADE, related_name="programme_lines"
    )

    year_level = models.PositiveSmallIntegerField(
        choices=LEVEL_NUMBER.choices,
        null=True,
        blank=True,
        help_text="Academic year within the programme",
    )
    semester_no = models.PositiveSmallIntegerField(
        choices=SEMESTER_NUMBER.choices,
        null=True,
        blank=True,
        help_text="Semester slot in that year",
    )
    is_required = models.BooleanField(default=True)

    # This is here because it can vary per curricula
    credit_hours = models.PositiveSmallIntegerField(
        choices=CREDIT_NUMBER.choices,
        null=True,
        blank=True,
        help_text="Credits To be used in this curriculum",
    )

    @property
    def effective_credit_hours(self) -> int:
        """
        Credits to show on transcripts: curriculum override -or-
        fallback to the catalogue value.
        """
        return (
            self.credit_hours
            if self.credit_hours is not None
            else self.course.credit_hours
        )

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.curriculum} <-> {self.course}"

    def save(self, *args, **kwargs) -> None:
        if self.credit_hours is None:
            self.credit_hours = self.course.credit_hours

        if self.year_level is None:
            # Extract first digit from course.number to set default year_level
            number_str = str(self.course.number).strip()
            if number_str.isdigit():
                self.year_level = int(number_str[0])
            else:
                raise ValueError(
                    f"Invalid course.number '{self.course.number}' for deriving year_level"
                )

        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("curriculum", "course"), name="uniq_course_per_curriculum"
            )
        ]
        ordering = ["curriculum", "year_level", "semester_no"]
