"""Course module."""

from __future__ import annotations

from django.db import models

from app.academics.choices import CREDIT_NUMBER, LEVEL_NUMBER
from app.shared.utils import make_course_code
from app.academics.models.curriculum import Curriculum


class Course(models.Model):
    """University catalogue entry describing a single course offering.

    Example:
        >>> from app.academics.models import Course, College
        >>> coas = College.objects.create(code="COAS", long_name="College of Arts and Sciences")
        >>> Course.objects.create(name="MATH", number="101", title="Algebra", college=coas)

    Side Effects:
        ``save()`` populates ``code`` from ``name`` and ``number``.
    """

    code = models.CharField(max_length=20, editable=False)
    number = models.CharField(max_length=10)  # e.g. 101
    title = models.CharField(max_length=255)
    description: models.TextField = models.TextField(blank=True)
    credit_hours = models.PositiveSmallIntegerField(
        default=CREDIT_NUMBER.THREE, choices=CREDIT_NUMBER.choices, blank=True
    )
    departments = models.ManyToManyField(  # eg. MATH
        "academics.Department", related_name="courses", blank=False
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
        """Human-friendly year level derived from the first digit of the course number.

        Returns the enum *label* or "other" when the pattern does not match a known level.
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
        """Populate ``code`` from ``name`` and ``number`` before saving."""
        dept_code = f"{self.departments}"
        self.code = make_course_code(dept_code, number=self.number)
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover
        """Return the ``CODE - Title`` representation."""
        return f"{self.code} - {self.title}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["code", "college"],
                name="uniq_course_code_per_college",
            ),
        ]
