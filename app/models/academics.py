from __future__ import annotations

from django.db import models
from django.core.exceptions import ValidationError
from django.db.models.functions import Lower
from app.constants import (
    CURRICULUM_LEVEL_CHOICES,
    COLLEGE_CHOICES,
)
from app.models.utils import validate_model_status, make_choices
from django.contrib.contenttypes.fields import GenericRelation

# ------------------------------------------------------------------
# College and Curriculum
# ------------------------------------------------------------------


class College(models.Model):
    code = models.CharField(max_length=4, unique=True)
    fullname = models.CharField(max_length=255)

    def clean(self) -> None:
        if (self.code, self.fullname) not in COLLEGE_CHOICES:
            raise ValidationError("Invalid (code, fullname) pair for College.")

    @property
    def current_dean(self):
        ra = (
            self.role_assignments.filter(role="Dean", end_date__isnull=True)
            .order_by("-start_date")
            .select_related("user")
            .first()
        )
        return ra.user if ra else None

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code} - {self.fullname}"


class Curriculum(models.Model):
    title = models.CharField(max_length=255)
    level = models.CharField(
        max_length=15, choices=make_choices(CURRICULUM_LEVEL_CHOICES)
    )
    college = models.ForeignKey(
        "app.College", on_delete=models.CASCADE, related_name="curricula"
    )
    academic_year = models.ForeignKey(
        "app.AcademicYear", on_delete=models.PROTECT, related_name="curricula"
    )
    is_active = models.BooleanField(default=False)

    status_history = GenericRelation("app.StatusHistory", related_query_name="curriculum")

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.title} - {self.level} - {self.college}"

    def _add_status(
        self,
        state,
        author,
    ):
        """
        Convenience wrapper to append a new Status row.
        """
        return self.status_history.create(
            state=state,
            author=author,
        )

    def set_status_revision(
        self,
        author,
    ):
        """
        Convenience wrapper to append a new revision Status row.
        """
        return self._add_status(state="needs_revision", author=author)

    def set_status_approved(
        self,
        author,
    ):
        """
        Convenience wrapper to append a new Approved Status row.
        """
        return self._add_status(state="approved", author=author)

    def set_status_pending(
        self,
        author,
    ):
        """
        Convenience wrapper to append a new Pending Status row.
        """
        return self._add_status(state="pending", author=author)

    def current_status(self):
        """Return most recent status entry (or None)."""
        return self.status_history.order_by("-created_at").first()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["level", "college", "academic_year"],
                condition=models.Q(is_active=True),
                name="uniq_active_curriculum_level_college",
            )
        ]


# ------------------------------------------------------------------
# Course and Prerequisite
# ------------------------------------------------------------------


class Course(models.Model):
    name = models.CharField(max_length=10)  # e.g. MATH
    number = models.CharField(max_length=10)  # e.g. 101
    title = models.CharField(max_length=255)
    code = models.CharField(max_length=20, editable=False)
    description: models.TextField = models.TextField(blank=True)
    credit_hours: models.PositiveSmallIntegerField = models.PositiveSmallIntegerField()
    curriculum = models.ForeignKey(
        Curriculum, related_name="courses", on_delete=models.PROTECT
    )

    prerequisites: models.ManyToManyField["Course", "Prerequisite"] = (
        models.ManyToManyField(
            "self",
            symmetrical=False,
            through="Prerequisite",
            related_name="dependent_courses",
            blank=True,
        )
    )

    # ---------- hooks ----------
    def save(self, *args, **kwargs):
        """
        updating course_code on the fly
        """
        self.code = f"{self.name}{self.number}"
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("code"), "curriculum", name="uniq_course_code_per_curriculum"
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code} - {self.title}"

    def clean(self):
        super().clean()
        validate_model_status(self)


class Prerequisite(models.Model):
    course = models.ForeignKey(
        Course, related_name="course_prereq_edges", on_delete=models.CASCADE
    )
    prerequisite_course = models.ForeignKey(
        Course, related_name="required_for_edges", on_delete=models.CASCADE
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course", "prerequisite_course"], name="uniq_prerequisite_pair"
            ),
            models.CheckConstraint(
                check=~models.Q(course=models.F("prerequisite_course")),
                name="no_self_prerequisite",
            ),
        ]

    def clean(self) -> None:
        if Prerequisite.objects.filter(
            course=self.prerequisite_course, prerequisite_course=self.course
        ).exists():
            raise ValidationError("Circular prerequisite detected.")
