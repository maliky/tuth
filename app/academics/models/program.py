"""Curriculum course module."""

from __future__ import annotations
from typing import Self

from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from django.db import models

from app.academics.choices import CREDIT_NUMBER


class Program(models.Model):
    """Map Curriculum instances to their constituent courses.

    Example:
        >>> Program.objects.create(curriculum=curriculum, course=course)

    Side Effects:
        save() defaults credit_hours to the course value when missing.
    """

    curriculum = models.ForeignKey(
        "academics.Curriculum", on_delete=models.CASCADE, related_name="programs"
    )
    course = models.ForeignKey(
        "academics.Course", on_delete=models.CASCADE, related_name="in_programs"
    )
    is_required = models.BooleanField(default=True)

    # credit hours depend on the curricula not the Course, so It moved from course to here.
    credit_hours = models.PositiveSmallIntegerField(
        choices=CREDIT_NUMBER.choices,
        help_text="Credits to be used in this curriculum for this course",
        default=CREDIT_NUMBER.THREE,
    )

    def __str__(self) -> str:  # pragma: no cover
        """Return Curriculum <-> Course for readability."""
        return f"{self.course} in --> <-- has {self.curriculum}"

    @classmethod
    def get_default(cls, course=None) -> Self:
        """Returns a default (unique) Program."""
        if not course:
            course = Course.get_default()
        def_curriculum = Curriculum.get_default()
        def_pg, _ = cls.objects.get_or_create(curriculum=def_curriculum, course=course)
        return def_pg

    def get_unique_default(cls) -> Self:
        """Returns a default (unique) Program."""
        dft_course = Course.get_default()
        return cls.get_default(course=dft_course)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("curriculum", "course"), name="uniq_course_per_curriculum"
            )
        ]
        ordering = ["curriculum"]
