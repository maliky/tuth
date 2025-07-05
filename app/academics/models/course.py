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

    # ~~~~~~~~ Mandatory ~~~~~~~~
    number = models.CharField(max_length=10)  # e.g. 101

    # ~~~~ Auto-filled ~~~~
    department = models.ForeignKey(
        "academics.Department",
        on_delete=models.CASCADE,
        related_name="courses",
    )

    # ~~~~ Read-only ~~~~
    code = models.CharField(max_length=20, editable=False)

    # ~~~~~~~~ Optional ~~~~~~~~
    short_code = models.CharField(max_length=20, editable=True, null=True, blank=True)
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
        return f"{self.short_code} - {self.title}"

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

    def _ensure_codes(self):
        if not self.code:
            self.code = make_course_code(self.department, number=self.number)
        if not self.short_code:
            self.short_code = make_course_code(
                self.department, number=self.number, short=True
            )

    def _ensure_dept(self):
        if not self.department_id:
            self.department = Department.get_default()

    # > TODO: get the list of teachers for this course.sections during the current semester.
    # > TODO: get the list of student enrolled in this course.sections during the current semester.

    # ---------- hooks ----------
    def save(self, *args, **kwargs) -> None:
        """Populate code from department short_name and number before saving."""
        self._ensure_dept()
        self._ensure_codes()
        super().save(*args, **kwargs)

    @classmethod
    def for_curriculum(cls, curriculum) -> CourseQuery:
        """Return courses included in the given curriculum."""
        return cls.objects.filter(curricula=curriculum).distinct()

    @classmethod
    def get_default(cls, number: str = "0000") -> Self:
        """Return a default Course."""
        def_crs, _ = cls.objects.get_or_create(
            department=Department.get_default(),
            number=number,
            title=f"Default Course {number}",
        )
        return def_crs

    @classmethod
    def get_unique_default(cls) -> Self:
        """Return a default Course which is unique. A most 1000 course can be created."""
        number = f"{next(DEFAULT_COURSE_NO):04d}"
        return cls.get_default(number=number)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["department", "number"],
                name="uniq_course_number_per_department",
            ),
        ]
