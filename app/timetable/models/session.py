"""Session module."""

from __future__ import annotations

from django.db import models

from app.shared.enums import WEEKDAYS_NUMBER


class Schedule(models.Model):
    weekday = models.PositiveSmallIntegerField(
        choices=WEEKDAYS_NUMBER.choices,
        help_text="Week day number (Monday=1, Tuesday=2, …)",
    )
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)

    def __str__(self):
        """Return ``weekday: start-end`` for quick inspection in admin."""
        # can we shorten weekday to only have the first 3 char?
        return f"{self.weekday}: {self.start_time}-{self.end_time}"

    @property
    def weekday_name(self) -> str:
        """
        Return the human‐readable name of this schedule’s weekday,
        e.g. "Monday", "Tuesday", etc.
        """
        return self.get_weekday_display()

    @property
    def start_time_str(self) -> str:
        """Start time formatted as ``HH:MM``."""
        return self.start_time.strftime("%H:%M")

    @property
    def end_time_str(self) -> str:
        """End time formatted as ``HH:MM`` or empty string."""
        return self.end_time.strftime("%H:%M") if self.end_time else ""

    # > validation end_time should alway be bigger than start_time
    # ? need to check that there no overlap. may need to store duration
    # and implement a non overlap function like for semester and terms.
    def clean(self) -> None:
        """Check that the date are correct"""
        if self.end_time is not None:
            assert self.start_time < self.end_time, "start_time must be before end_time"


class Session(models.Model):
    """
    A “meeting slot” for a Section:
      - weekday (1=Monday … 7=Sunday)
      - start_time / end_time
      - space (Room)
      - which Section this slot belongs to
    """

    room = models.ForeignKey("spaces.Room", on_delete=models.PROTECT)
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
        """Return ``Schedule, Room`` for use in admin lists."""
        return f"{self.schedule}, {self.room}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["room", "schedule"],
                name="uniq_schedule_per_room",
            )
        ]
        indexes = [
            models.Index(fields=["room", "schedule"]),
        ]
