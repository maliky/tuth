"""Course module."""

from __future__ import annotations

from itertools import count
from typing import Self

from django.db import models

from app.academics.choices import LEVEL_NUMBER
from app.academics.models.department import Department
from app.shared.utils import make_course_code
from app.shared.types import CourseQuery

DEFAULT_COURSE_NO = count(start=1, step=1)


class Course(models.Model):
    """University catalogue entry describing a single course offering.

    Example:
        >>> COAS = College.get_default()
        >>> MATH = Departement.objects.create(code="COAS", long_name="College of Arts and Sciences")
        >>> Course.objects.create(name="MATH", number="101", title="Algebra", college=coas)

    Side Effects:
        save() populates code from name and number.
    """

    department = models.ForeignKey(
        "academics.Department",
        on_delete=models.CASCADE,
        related_name="courses",
    )
    number = models.CharField(max_length=10)  # e.g. 101

    # the above combined make a unique code, its mainly for backward compatibility
    code = models.CharField(max_length=20, editable=False)

    title = models.CharField(max_length=255, blank=True, null=True)

    description: models.TextField = models.TextField(blank=True, null=True)
    prerequisites = models.ManyToManyField(
        "self",
        symmetrical=False,
        through="academics.Prerequisite",
        related_name="dependent_courses",
        blank=True,
    )

    def __str__(self) -> str:  # pragma: no cover
        """Return the CODE - Title representation."""
        return f"{self.code} - {self.title}"

    @property
    def level(self) -> str:
        """Human-friendly year level derived from the first digit of the course number.

        Returns the enum label or "other" when the pattern does not match a known level.
        """
        try:
            digit = int(self.number.strip()[0])  # "101" → 1
            return LEVEL_NUMBER(digit).label  # "freshman"
        except (ValueError, IndexError):  # non-digit / empty
            return "other"
        except KeyError:  # digit ∉ enum
            return "other"

    def _ensure_code(self):
        if not self.code:
            self.code = make_course_code(self.department, number=self.number)

    def _ensure_dept(self):
        if not self.department_id:
            self.department = Department.get_default()

    # ---------- hooks ----------
    def save(self, *args, **kwargs) -> None:
        """Populate code from department short_name and number before saving."""
        self._ensure_dept()
        self._ensure_code()
        super().save(*args, **kwargs)

    @classmethod
    def for_curriculum(cls, curriculum) -> CourseQuery:
        """Return courses included in the given curriculum."""
        return cls.objects.filter(curricula=curriculum).distinct()

    @classmethod
    def get_default(cls, number: int = 0) -> Self:
        """Return a default Course."""
        def_crs, _ = cls.objects.get_or_create(
            department=Department.get_default(),
            number=f"{number:04d}",
            title=f"Default Course {number:04d}",
        )
        return def_crs

    @classmethod
    def get_unique_default(cls) -> Self:
        """Return a default Course which is unique. A most 1000 course can be created."""
        return cls.get_default(number=next(DEFAULT_COURSE_NO))

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["department", "number"],
                name="uniq_course_number_per_department",
            ),
        ]
