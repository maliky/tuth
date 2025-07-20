"""College module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models
from simple_history.models import HistoricalRecords

from app.academics.choices import (
    CollegeCodeChoices,
    CollegeLongNameChoices,
    LEVEL_NUMBER,
)

if TYPE_CHECKING:  # pragma: no cover - avoid circular imports at runtime
    from app.academics.models import Course, Curriculum, Department
    from app.people.models.student import Student
    from app.people.models.staffs import Faculty
    from app.people.models.role_assignment import RoleAssignment


class College(models.Model):
    """Institutional unit responsible for a set of programmes.

    Example: See get_default

    Side Effects:
        save() sets long_name based on code.
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    code = models.CharField(
        max_length=4,
        choices=CollegeCodeChoices.choices,
        default=CollegeCodeChoices.COAS,
    )

    # ~~~~ Auto-filled ~~~~
    long_name = models.CharField(
        max_length=50,
        # choices=CollegeLongNameChoices.choices,
        blank=True,
    )
    history = HistoricalRecords()

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code}"

    # > TODO get some properties to list the number of unique enrolled students per
    # level freshman, sophomore, junior, senior
    # the name of the departments (with name of chairs)
    # the name of the curriculum
    # the number of faculties
    # the number of unique courses offered by that college.

    @classmethod
    def get_default(cls) -> College:
        """Return the default college ie. COAS."""
        # will set the long_name by default on save
        def_clg, _ = cls.objects.get_or_create(code=CollegeCodeChoices.DEFT)
        return def_clg

    def _ensure_long_name(self) -> None:
        """Set the long name base on the college code if none where provided."""
        if not self.long_name:
            self.long_name = CollegeLongNameChoices[self.code.upper()].label

    def save(self, *args, **kwargs) -> None:
        """Ensure long_name matches the selected code before saving."""
        self._ensure_long_name()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # computed properties
    # ------------------------------------------------------------------

    @property
    def student_counts_by_level(self) -> str:
        """Return number of students grouped by class level."""
        from app.people.models.student import Student

        counts = {lv.label: 0 for lv in LEVEL_NUMBER}
        for stud in Student.objects.filter(curriculum__college=self):
            credits = stud.completed_credits
            if credits <= 36:
                level = LEVEL_NUMBER.ONE.label
            elif credits <= 72:
                level = LEVEL_NUMBER.TWO.label
            elif credits <= 108:
                level = LEVEL_NUMBER.THREE.label
            else:
                level = LEVEL_NUMBER.FOUR.label
            counts[level] += 1
        return ", ".join(f"{lvl}: {cnt}" for lvl, cnt in counts.items())

    @property
    def department_chairs(self) -> str:
        """Return departments with their current chair names."""
        from app.people.choices import UserRole
        from app.people.models.role_assignment import RoleAssignment

        result: list[str] = []
        for dept in self.departments.all():
            chair = (
                RoleAssignment.objects.filter(
                    department=dept,
                    role=UserRole.CHAIR,
                    end_date__isnull=True,
                )
                .select_related("user")
                .first()
            )
            chair_name = chair.user.get_full_name() if chair else ""
            result.append(f"{dept.short_name}: {chair_name}")
        return ", ".join(result)

    @property
    def curricula_names(self) -> str:
        """Return curriculum short names for this college."""
        names = self.curricula.values_list("short_name", flat=True)
        return ", ".join(names)

    @property
    def faculty_count(self) -> int:
        """Return number of faculty members in the college."""
        from app.people.models.staffs import Faculty

        return Faculty.objects.filter(college=self).count()

    @property
    def course_count(self) -> int:
        """Return number of distinct courses offered."""
        from app.academics.models.course import Course

        return Course.objects.filter(department__college=self).distinct().count()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["code"], name="unique_college_code"),
            models.UniqueConstraint(fields=["long_name"], name="unique_college_name"),
        ]
        ordering = ["code"]
