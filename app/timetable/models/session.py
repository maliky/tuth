"""Session module."""

from __future__ import annotations

from django.db import models
from django.forms import ValidationError


class Session(models.Model):
    """A meeting slot for a Section.

    Example:
        >>> Session.objects.create(room=room, schedule=schedule, section=section)
    """

    room = models.ForeignKey("spaces.Room", on_delete=models.PROTECT)

    # I have to be carrefull about TBA schedules, the may raise uniq constraint
    schedule = models.ForeignKey(
        "timetable.Schedule",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="schedules",
    )
    section = models.ForeignKey(
        "timetable.Section",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sessions",
    )

    @property
    def weekday(self):
        """Shortcut to the schedule's weekday."""
        return self.schedule.weekday if self.schedule else ""

    @property
    def start_time(self):
        """Shortcut to the schedule's starting time."""
        return self.schedule.start_time if self.schedule else ""

    @property
    def end_time(self):
        """Shortcut to the schedule's ending time."""
        return self.schedule.end_time if self.schedule else ""

    def __str__(self):
        """Return Schedule, Room for use in admin lists."""
        return f"{self.schedule}, {self.room}"

    def schedule_is_set(self):
        """Return true a the schedule is set."""
        return self.schedule is not None and self.schedule.is_set()

    # No constraints for now. because how to handle TBA
    # class Meta:
    #     constraints = [
    #         models.UniqueConstraint(
    #             fields=["room", "schedule"],
    #             name="uniq_schedule_per_room",
    #         )
    #     ]
    #     indexes = [
    #         models.Index(fields=["room", "schedule"]),
    #     ]

    def clean(self) -> None:
        """Ensure no overlapping session exists for the same room."""
        super().clean()

        if self.schedule is None:
            return
        # ie overlap possible for TBA or start_time < 8:00 AM.
        if not self.schedule_is_set() and not self.room:
            return

        start = self.schedule.start_time
        end = self.schedule.end_time

        if start and end:
            clash = Session.objects.filter(
                room=self.room,
                schedule__weekday=self.schedule.weekday,
                schedule__start_time__lt=end,
                schedule__end_time__gt=start,
            ).exclude(pk=self.pk)

            if clash.exists():
                raise ValidationError({"schedule": "Overlapping session for this room."})
