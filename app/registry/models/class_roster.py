from __future__ import (
    annotations,
)

from app.people.models.profile import StudentProfile
from app.shared.constants.choices import StatusRegistration
from django.db import models
from django.db.models import QuerySet


class ClassRoster(models.Model):
    """Container for the list of students enrolled in a section."""

    section = models.OneToOneField("timetable.Section", on_delete=models.CASCADE)
    last_updated = models.DateTimeField(auto_now=True)

    @property
    def students(self) -> QuerySet[StudentProfile]:
        """Return all users registered to this section."""
        return StudentProfile.objects.filter(
            registrations__section=self.section,
            registrations__status=StatusRegistration.COMPLETED,
        )
