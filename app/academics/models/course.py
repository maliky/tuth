"""Course module."""

from __future__ import annotations

from itertools import count
from typing import Self

from django.apps import apps
from django.db import models
from simple_history.models import HistoricalRecords

from app.academics.choices import LEVEL_NUMBER
from app.academics.models.department import Department
from app.shared.types import CourseQuery
from app.shared.utils import make_course_code
from app.timetable.utils import get_current_semester

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
    history = HistoricalRecords()
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

    def current_faculty(self):
        """Get the list of faculty teaching this course in the current semester."""
        Faculty = apps.get_model("people", "Faculty")

        # Returning Any from function declared to return "QuerySet[Faculty, Faculty] | None"  [no-any-return]
        # when adding the  type hint  '-> FacultyQuery | None:'
        # >TODO Try to fix this and add StudentQuery type hint to the next method too.

        semester = get_current_semester()
        if semester is None:
            return Faculty.objects.none()
        return Faculty.objects.filter(
            section__semester=semester, section__program__course=self
        ).distinct()

    def current_students(self):
        """Returns the list of student taking this course during the current semester."""
        Student = apps.get_model("people", "Student")

        semester = get_current_semester()
        if semester is None:
            return Student.objects.none()
        return Student.objects.filter(
            student_registrations__section__semester=semester,
            student_registrations__section__program__course=self,
        ).distinct()

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
