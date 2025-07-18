"""Class roster module."""

from __future__ import annotations

from django.db import models
from app.shared.types import StudentProfileQuery

from app.people.models.student import Student
from app.registry.choices import StatusRegistration


class ClassRoster(models.Model):
    """Container for the list of students enrolled in a section.

    Example:
        >>> from app.registry.models.class_roster import ClassRoster
        >>> roster = ClassRoster.objects.create(section=section)
        >>> roster.students.count()
        0
    """

    # ~~~~~~~~ Mandatory ~~~~~~~~
    section = models.OneToOneField("timetable.Section", on_delete=models.CASCADE)

    # ~~~~ Auto-filled ~~~~
    last_updated = models.DateTimeField(auto_now=True)

    @property
    def students(self) -> StudentProfileQuery:
        """Return all users registered to this section."""
        return Student.objects.filter(
            student_registrations__section=self.section,
            student_registrations__status=StatusRegistration.COMPLETED,
        )
