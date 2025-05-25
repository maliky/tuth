from __future__ import (
    annotations,
)

from django.db import models
from django.contrib.auth.models import User


class ClassRoster(models.Model):
    """Container for the list of students enrolled in a section."""

    section = models.OneToOneField("timetable.Section", on_delete=models.CASCADE)
    updated_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="rosters_updated"
    )
    last_updated = models.DateTimeField(auto_now=True)

    @property
    def students(self):
        """Return all users registered to this section."""
        return User.objects.filter(
            registration__section=self.section
        )  # or self.section.registration_set
