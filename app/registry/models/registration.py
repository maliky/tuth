"""Registration module."""

from __future__ import annotations

from django.db import models

from app.registry.choices import StatusRegistration
from app.shared.status.mixins import StatusableMixin


class Registration(StatusableMixin, models.Model):
    """Enrollment of a student in a course section.

    Example:
        >>> from app.registry.models.registration import Registration
        >>> reg = Registration.objects.create(
        ...     student=student_profile,
        ...     section=section_factory(1),
        ... )
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    student = models.ForeignKey(
        "people.Student",
        on_delete=models.CASCADE,
        related_name="student_registrations",
    )
    section = models.ForeignKey(
        "timetable.Section",
        on_delete=models.CASCADE,
        related_name="section_registrations",
    )

    # ~~~~ Auto-filled ~~~~
    # this is optional and I could get it through the SatusableMixin
    status = models.CharField(
        max_length=30,
        choices=StatusRegistration.choices,
        default=StatusRegistration.PENDING,
    )
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
