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
        # can we shorten weekday to only have the first 3 char?
        return f"{self.weekday}: {self.start_time}-{self.end_time}"

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
        return self.schedule.weekday

    @property
    def start_time(self):
        return self.schedule.start_time

    @property
    def end_time(self):
        return self.schedule.end_time

    def __str__(self):
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
