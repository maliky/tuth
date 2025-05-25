from __future__ import (
    annotations,
)

from django.contrib.auth.models import User
from django.db import models

from app.shared.constants import STATUS_CHOICES_PER_MODEL
from app.shared.utils import make_choices


class Registration(models.Model):
    """Enrollment of a student in a course section."""

    student = models.ForeignKey(User, on_delete=models.CASCADE)
    section = models.ForeignKey("timetable.Section", on_delete=models.CASCADE)
    status = models.CharField(
        max_length=30,
        choices=make_choices(STATUS_CHOICES_PER_MODEL["registration"]),
        default="pre_registered",
    )
    date_registered = models.DateTimeField(auto_now_add=True)
    date_pre_registered = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "section"],
                name="uniq_registration_student_section",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.student} – {self.section} -  {self.status}"
