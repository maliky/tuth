"""Course module."""

from __future__ import annotations

from django.db import models

from app.shared.enums import CREDIT_NUMBER, LEVEL_NUMBER
from app.shared.utils import make_course_code
from app.academics.models.curriculum import Curriculum


class Course(models.Model):
    """Catalog entry defining a unit of instruction."""

    code = models.CharField(max_length=20, editable=False)
    name = models.CharField(max_length=10)  # e.g. MATH
    number = models.CharField(max_length=10)  # e.g. 101
    title = models.CharField(max_length=255)
    description: models.TextField = models.TextField(blank=True)
    credit_hours = models.PositiveSmallIntegerField(
        default=CREDIT_NUMBER.THREE, choices=CREDIT_NUMBER.choices, blank=True
    )

    # the college responsible for this course
    college = models.ForeignKey(
        "academics.College",
        on_delete=models.PROTECT,
        related_name="courses",
    )
    prerequisites = models.ManyToManyField(
        "self",
        symmetrical=False,
        through="academics.Prerequisite",
        related_name="dependent_courses",
        blank=True,
    )

    @property
    def level(self) -> str:
        """
        Human-friendly year level derived from the first digit of
        the course number – returns the enum *label* or "other"
        when the pattern does not match a known level.
        """
        try:
            digit = int(self.number.strip()[0])  # "101" → 1
            return LEVEL_NUMBER(digit).label  # "freshman"
        except (ValueError, IndexError):  # non-digit / empty
            return "other"
        except KeyError:  # digit ∉ enum
            return "other"

    @classmethod
    def for_curriculum(cls, curriculum: Curriculum) -> models.QuerySet:
        """Return courses included in the given curriculum."""
        return cls.objects.filter(curricula=curriculum).distinct()

    # ---------- hooks ----------
    def save(self, *args, **kwargs) -> None:
        """
        updating course_code on the fly
        """
        self.code = make_course_code(name=self.name, number=self.number)
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code} - {self.title}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["code", "college"],
                name="uniq_course_code_per_college",
            ),
        ]
