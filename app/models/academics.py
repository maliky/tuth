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
    courses = models.ManyToManyField(
        "app.Course",
        through="app.CurriculumCourse",
        related_name="curricula",  # <── reverse accessor course.curricula
        blank=True,
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
                fields=["college", "title"],
                condition=models.Q(is_active=True),
                name="uniq_active_curriculum_college",
            )
        ]


# app/models/academics.py  (same file as Course / Curriculum)


class CurriculumCourse(models.Model):
    """
    Junction table between Curriculum and Course.
    You can extend it with fields such as `semester_level`,
    `is_required`, `order_in_semester`,
    """

    curriculum = models.ForeignKey(
        "app.Curriculum", on_delete=models.CASCADE, related_name="programme_lines"
    )
    course = models.ForeignKey(
        "app.Course", on_delete=models.CASCADE, related_name="programme_lines"
    )

    year_level = models.PositiveSmallIntegerField(
        choices=LEVEL_CHOICES.choices,
        null=True,
        blank=True,
        help_text="Academic year within the programme",
    )
    semester_no = models.PositiveSmallIntegerField(
        choices=SEMESTER_NUMBER.choices,
        null=True,
        blank=True,
        help_text="Semester slot in that year",
    )
    is_required = models.BooleanField(default=True)

    # This is here because it can vary per curricula
    credit_hours = models.PositiveSmallIntegerField(
        choices=CREDIT_CHOICES.choices,
        null=True,
        blank=True,
        help_text="Credits To be used in this curriculum",
    )

    @property
    def effective_credit_hours(self) -> int:
        """
        Credits to show on transcripts: curriculum override -or-
        fallback to the catalogue value.
        """
        return (
            self.credit_hours
            if self.credit_hours is not None
            else self.course.credit_hours
        )

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.curriculum} <-> {self.course}"

    def save(self, *args, **kwargs):
        if self.credit_hours is None:
            self.credit_hours = self.course.credit_hours
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("curriculum", "course"), name="uniq_course_per_curriculum"
            )
        ]
        ordering = ["curriculum", "year_level", "semester_no"]


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

    # the college responsible for this course
    college = models.ForeignKey(
        "app.College",
        on_delete=models.PROTECT,
        related_name="courses",
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
        Human-friendly year level derived from the first digit of
        the course number – returns the enum *label* or "other"
        when the pattern does not match a known level.
        """
        try:
            digit = int(self.number.strip()[0])  # "101" → 1
            return LEVEL_CHOICES(digit).label  # "freshman"
        except (ValueError, IndexError):  # non-digit / empty
            return "other"
        except KeyError:  # digit ∉ enum
            return "other"

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
            ),
            models.UniqueConstraint(
                fields=["code", "curriculum"],
                name="uniq_course_code_per_curriculum",
            ),
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

