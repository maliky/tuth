"""Course module."""

from __future__ import annotations

from django.db import models

from app.academics.choices import CREDIT_NUMBER, LEVEL_NUMBER
from app.shared.utils import make_course_code
from app.academics.models.curriculum import Curriculum


class Course(models.Model):
    """University catalogue entry describing a single course offering.

    Example:
        >>> from app.academics.models import Course, Department, College
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
    # the 2 above make the code
    code = models.CharField(max_length=20, editable=False)
    # with college must be unique.

    credit_hours = models.PositiveSmallIntegerField(
        default=CREDIT_NUMBER.THREE, choices=CREDIT_NUMBER.choices
    )
    title = models.CharField(max_length=255, blank=True, null=True)
    description: models.TextField = models.TextField(blank=True, null=True)
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

        Returns the enum label or "other" when the pattern does not match a known level.
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

    def _set_code(self):
        if not self.code:
            dept_short_name = f"{self.department.short_name}"
            self.code = make_course_code(dept_short_name, number=self.number)

    # ---------- hooks ----------
    def save(self, *args, **kwargs) -> None:
        """Populate code from department short_name and number before saving."""
        self._set_code()
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover
        """Return the CODE - Title representation."""
        return f"{self.code} - {self.title}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["department", "number"],
                name="uniq_course_number_per_department",
            ),
        ]
