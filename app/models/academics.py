from __future__ import annotations

from django.db import models
from django.core.exceptions import ValidationError
from django.db.models.functions import Lower

# ------------------------------------------------------------------
# College and Curriculum
# ------------------------------------------------------------------

COLLEGE_CHOICES: list[tuple[str, str]] = [
    ("COHS", "College of Health Sciences"),
    ("COAS", "College of Arts and Sciences"),
    ("COED", "College of Education"),
    ("CAFS", "College of Agriculture and Food Sciences"),
    ("COET", "College of Engineering and Technology"),
    ("COBA", "College of Business Administration"),
]

VALIDATION_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("adjustments_required", "Adjustments Required"),
]

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
        max_length=15,
        choices=[
            ("freshman", "Freshman"),
            ("sophomore", "Sophomore"),
            ("junior", "Junior"),
            ("senior", "Senior"),
        ],
    )
    college = models.ForeignKey(
        College, on_delete=models.CASCADE, related_name="curricula"
    )
    created_by = models.ForeignKey(
        "auth.User",
        null=True,
        on_delete=models.SET_NULL,
        related_name="curricula_created",
    )
    validated_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="curricula_validated",
    )
    validation_status = models.CharField(
        max_length=50,
        choices= VALIDATION_STATUS_CHOICES,
        default="pending",
    )
    is_active = models.BooleanField(default=False)
    creation_date = models.DateTimeField(auto_now_add=True)
    validation_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["level", "college"],
                condition=models.Q(is_active=True),
                name="uniq_active_curriculum_level_college",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.title} - {self.level} - {self.college}"


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
