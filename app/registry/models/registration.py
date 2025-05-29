from __future__ import (
    annotations,
)

from django.db import models

from app.shared.constants.registry import StatusRegistration


class Registration(models.Model):
    """Enrollment of a student in a course section."""

    student = models.ForeignKey("people.StudentProfile", on_delete=models.CASCADE)
    section = models.ForeignKey("timetable.Section", on_delete=models.CASCADE)
    status = models.CharField(
        max_length=30,
        choices=StatusRegistration.choices,
        default=StatusRegistration.PENDING,
    )
    # > to update with reservation date
    # > but what happen if the reservation is canceled.  Keep the field.
    date_latest_reservation = models.DateTimeField(null=True, blank=True)
    date_registered = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "section"],
                name="uniq_registration_student_section",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.student} – {self.section} -  {self.status}"
