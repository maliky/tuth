"""College module."""

from __future__ import annotations

from django.apps import apps
from django.db import models
from simple_history.models import HistoricalRecords

from app.academics.choices import LEVEL_NUMBER, COLLEGE_LONG_NAME
from app.shared.auth.perms import UserRole


class College(models.Model):
    """Institutional unit responsible for a set of Curris/Programs.

    Example: See get_dft

    Side Effects:
        save() sets long_name based on code.
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    code = models.CharField(default="DEFT")

    # ~~~~ auto-filled ~~~~
    long_name = models.CharField(
        max_length=50,
        # choices=CollegeLongNameChoices.choices,
        blank=True,
    )
    history = HistoricalRecords()

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code}"

    @classmethod
    def get_dft(cls) -> College:
        """Return the default college ie. COAS."""
        # will set the long_name by default on save
        def_clg, _ = cls.objects.get_or_create(code="DEFT")
        return def_clg

    def _ensure_long_name(self) -> None:
        """Set the long name base on the college code if none where provided."""
        # this is tricky if no CollegeLongnamechoices
        if not self.long_name:
            self.long_name = COLLEGE_LONG_NAME.get(self.code.lower(), "")

    def save(self, *args, **kwargs) -> None:
        """Ensure long_name matches the selected code before saving."""
        self._ensure_long_name()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # computed properties
    # ------------------------------------------------------------------

    @property
    def std_counts_by_level(self) -> str:
        """Return number of students grouped by class level."""
        Student = apps.get_model("people", "Student")

        counts = {lv.label: 0 for lv in LEVEL_NUMBER}
        for stud in Student.objects.filter(
            curriculum_enrollments__curriculum__college=self,
            curriculum_enrollments__is_primary=True,
        ).distinct():
            _credits = stud.completed_credits
            if _credits <= 36:
                level = LEVEL_NUMBER.ONE.label
            elif _credits <= 72:
                level = LEVEL_NUMBER.TWO.label
            elif _credits <= 108:
                level = LEVEL_NUMBER.THREE.label
            else:
                level = LEVEL_NUMBER.FOUR.label
            counts[level] += 1
        return ", ".join(f"{lvl}: {cnt}" for lvl, cnt in counts.items())

    @property
    def dpt_str(self) -> str:
        """Return departments of this college."""
        return ", ".join([f"{dept.code}" for dept in self.departments.all()])

    @property
    def curra_count(self) -> int:
        """Return number of curricula under this college."""
        return int(self.curricula.count())

    @property
    def faculty_count(self) -> int:
        """Return number of faculty members in the college."""
        Faculty = apps.get_model("people", "Faculty")
        return int(Faculty.objects.filter(college=self).count())

    @property
    def curra_names(self) -> str:
        """Return comma-separated curriculum short names for this college."""
        names = self.curricula.order_by("short_name").values_list("short_name", flat=True)
        return ", ".join(names)

    @property
    def dpt_chairs(self) -> str:
        """Return comma-separated department codes with assigned chairs."""
        RoleAssignment = apps.get_model("people", "RoleAssignment")
        dept_codes = (
            RoleAssignment.objects.filter(
                college=self, group__name=UserRole.CHAIR.value.label
            )
            .exclude(department__isnull=True)
            .values_list("department__code", flat=True)
            .distinct()
        )
        return ", ".join(dept_codes)

    @property
    def crs_count(self) -> int:
        """Return number of distinct courses offered."""
        return int(self.get_crss().count())

    def get_crss(self):
        """Return the list of distinc courses for this college.

        could be done with a loop on dept and dept.get_crss
        but not too efficient.
        """
        Course = apps.get_model("academics", "Course")
        return (
            Course.objects.filter(department__in=self.departments.all())
            .distinct()
            .order_by("number")
        )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["code"], name="unique_college_code"),
            models.UniqueConstraint(fields=["long_name"], name="unique_college_name"),
        ]
        ordering = ["code"]
