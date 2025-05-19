from __future__ import annotations

from django.db import models
from django.core.exceptions import ValidationError
from app.constants import LEVEL_CHOICES, COLLEGE_CHOICES, CREDIT_CHOICES
from app.models.utils import validate_model_status
from app.models.mixins import StatusableMixin
from app.app_utils import make_course_code
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


class Curriculum(StatusableMixin, models.Model):
    title = models.CharField(max_length=255)
    short_name = models.CharField(max_length=30, blank=True, null=True)

    college = models.ForeignKey(
        "app.College", on_delete=models.CASCADE, related_name="curricula"
    )
    # a constraint is that we should not have a curriculum in a college
    # created in the same year with same title
    creation_date = models.DateField()
    is_active = models.BooleanField(default=False)

    status_history = GenericRelation("app.StatusHistory", related_query_name="curriculum")

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.title} - {self.college}"

    def clean(self):
        super().clean()
        validate_model_status(self)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["college", "created_date"],
                condition=models.Q(is_active=True),
                name="uniq_active_curriculum_college",
            )
        ]


class Concentration(models.Model):
    """Optional major for a curriculum."""

    name = models.CharField(max_length=255)
    curriculum = models.ForeignKey(
        "app.curriculum",
        on_delete=models.CASCADE,
        related_name="concentrations",
    )

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} ({self.curriculum})"


# ------------------------------------------------------------------
# Course and Prerequisite
# ------------------------------------------------------------------


class Course(models.Model):
    name = models.CharField(max_length=10)  # e.g. MATH
    number = models.CharField(max_length=10)  # e.g. 101
    title = models.CharField(max_length=255)
    code = models.CharField(max_length=20, editable=False)
    description: models.TextField = models.TextField(blank=True)
    credit_hours = models.PositiveSmallIntegerField(
        default=CREDIT_CHOICES.THREE,
        choices=CREDIT_CHOICES.choices,
    )

    college = models.ForeignKey(
        "app.College",
        on_delete=models.PROTECT,
        related_name="courses",
    )
    curricula: models.ManyToManyField["Curriculum", "Course"] = models.ManyToManyField(
        "app.Curriculum",
        related_name="courses",
        blank=True,
    )
    concentration = models.ManyToManyField(
        "app.Concentration",
        related_name="courses",
        blank=True,
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

    @property
    def level(self) -> str:
        """
        Return 'freshman' / 'sophomore' / … based on the first digit of
        `number`.  Falls back to 'other' when the pattern doesn’t match.
        """
        return LEVEL_CHOICES.get(self.number[:1], "other")

    @classmethod
    def for_curriculum(cls, curriculum: "Curriculum") -> models.QuerySet:
        "helper function. get the course for a specific curriculum"
        return cls.objects.filter(curricula=curriculum).distinct()

    # ---------- hooks ----------
    def save(self, *args, **kwargs):
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
            )
        ]


class Prerequisite(models.Model):
    course = models.ForeignKey(
        Course, related_name="course_prereq_edges", on_delete=models.CASCADE
    )
    prerequisite_course = models.ForeignKey(
        Course, related_name="required_for_edges", on_delete=models.CASCADE
    )
    curriculum = models.ForeignKey(
        "app.Curriculum",
        on_delete=models.CASCADE,
        related_name="prerequisites",
        null=True,
        blank=True,
    )

    def clean(self) -> None:
        if Prerequisite.objects.filter(
            course=self.prerequisite_course, prerequisite_course=self.course
        ).exists():
            raise ValidationError("Circular prerequisite detected.")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["curriculum", "course", "prerequisite_course"],
                name="uniq_prerequisite_per_curriculum",
            ),
            models.CheckConstraint(
                check=~models.Q(course=models.F("prerequisite_course")),
                name="no_self_prerequisite",
            ),
        ]
