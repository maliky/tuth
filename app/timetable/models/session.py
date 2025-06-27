"""Session module."""

from __future__ import annotations

from app.timetable.choices import WEEKDAYS_NUMBER
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

    def __str__(self):
        """Return Schedule, Room for use in admin lists."""
        return f"{self.schedule}, {self.room}"

    @property
    def weekday(self):
        """Shortcut to the schedule's weekday."""
        return getattr(self.schedule, "weekday", WEEKDAYS_NUMBER.TBA)

    @property
    def start_time(self):
        """Shortcut to the schedule's starting time."""
        return getattr(self.schedule, "start_time", None)

    @property
    def end_time(self):
        """Shortcut to the schedule's ending time."""
        return getattr(self.schedule, "end_time", None)

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

        if self.schedule_id is None:
            return
        # ie overlap possible for TBA or start_time < 8:00 AM.
        if not self.room_id:
            return

        start = self.schedule.start_time  # type: ignore[union-attr]
        end = self.schedule.end_time  # type: ignore[union-attr]
        weekday = getattr(self.schedule, "weekday", WEEKDAYS_NUMBER.TBA)

        if start and end:
            clash = Session.objects.filter(
                room=self.room,
                schedule__weekday=weekday,
                schedule__start_time__lt=end,
                schedule__end_time__gt=start,
            ).exclude(pk=self.pk)

            if clash.exists():
                raise ValidationError({"schedule": "Overlapping session for this room."})
