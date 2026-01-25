"""Registration module."""

from __future__ import annotations

from app.shared.mixins import SimpleTableMixin
from django.db import models
from simple_history.models import HistoricalRecords
from typing import Self, cast

from app.shared.status.mixins import StatusableMixin


class Registration(StatusableMixin, models.Model):
    """Enrollment of a student in a course section with its status.

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
    status = models.ForeignKey(
        "registry.RegistrationStatus",
        on_delete=models.PROTECT,
        related_name="registrations",
    )
    date_registered = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.student} - {self.section}:{self.status}"

    def _ensure_registration_status(self):
        """Ensure a clearance status is set."""
        if not self.status_id:
            self.status = RegistrationStatus.get_default()

    def save(self, *args, **kwargs):
        """Check model before save."""
        self._ensure_registration_status()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "section"],
                name="uniq_registration_student_section",
            )
        ]
