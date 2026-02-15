"""Requirement groups for curriculum course prerequisite rules."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords


class ReqKind(models.TextChoices):
    """Requirement semantics attached to a curriculum course."""

    PREREQ_ALL = "prereq_all", "Prerequisite (all)"
    PREREQ_ANY = "prereq_any", "Prerequisite (any)"
    COREQ_ALL = "coreq_all", "Corequisite (all together)"


class CurriCourseReqGp(models.Model):
    """Group prerequisite/corequisite rules for one curriculum course."""

    curriculum_course = models.ForeignKey(
        "academics.CurriCourse",
        on_delete=models.CASCADE,
        related_name="requirement_groups",
    )
    kind = models.CharField(
        max_length=20,
        choices=ReqKind.choices,
        default=ReqKind.PREREQ_ALL,
        db_index=True,
    )
    label = models.CharField(max_length=80, blank=True)
    order = models.PositiveSmallIntegerField(default=0, db_index=True)
    history = HistoricalRecords()

    def __str__(self) -> str:  # pragma: no cover
        """Return a readable identifier for admin and logs."""
        target = self.curriculum_course
        return f"{target} [{self.get_kind_display()}]"

    def _ensure_label(self) -> None:
        """Set a stable default label for new groups."""
        if self.label:
            return
        # Keep labels deterministic so admin lists stay readable without manual input.
        next_index = (
            CurriCourseReqGp.objects.filter(curriculum_course=self.curriculum_course)
            .exclude(pk=self.pk)
            .count()
            + 1
        )
        self.label = f"{self.get_kind_display()} {next_index}"

    def save(self, *args, **kwargs) -> None:
        """Save requirement group with a deterministic default label."""
        self._ensure_label()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["curriculum_course", "order", "id"]


class CurriCourseReqMember(models.Model):
    """Single course member inside a requirement group.

    This explicit member model is effectively a through table. We could model
    this as a ManyToMany relation from group -> course with `through=...`, but
    keeping this first-class model makes ordering and future member metadata
    straightforward.
    """

    group = models.ForeignKey(
        "academics.CurriCourseReqGp",
        on_delete=models.CASCADE,
        related_name="members",
    )
    required_course = models.ForeignKey(
        "academics.Course",
        on_delete=models.CASCADE,
        related_name="requirement_group_memberships",
    )
    order = models.PositiveSmallIntegerField(default=0, db_index=True)
    history = HistoricalRecords()

    def __str__(self) -> str:  # pragma: no cover
        """Return a readable identifier for admin and logs."""
        return f"{self.group} -> {self.required_course}"

    def clean(self) -> None:
        """Block self-reference for grouped requirements."""
        if not self.group_id or not self.required_course_id:
            return
        # A target course cannot appear as its own prerequisite/corequisite member.
        target_course_id = self.group.curriculum_course.course_id
        if self.required_course_id == target_course_id:
            raise ValidationError({"required_course": "A course cannot require itself."})

    class Meta:
        ordering = ["group", "order", "required_course__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "required_course"],
                name="uniq_required_course_per_requirement_group",
            ),
        ]
