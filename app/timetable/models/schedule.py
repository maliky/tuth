"""Schedule module."""

from __future__ import annotations

from django.db import models

from app.shared.enums import WEEKDAYS_NUMBER


class Schedule(models.Model):
    """
    A “meeting slot” for a Section:
      - weekday (1=Monday … 7=Sunday)
      - start_time / end_time
      - space (Room)
      - which Section this slot belongs to
    """

    weekday = models.PositiveSmallIntegerField(
        choices=WEEKDAYS_NUMBER.choices,
        help_text="Week day number (Monday=1, Tuesday=2, …)",
    )
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    room = models.ForeignKey(
        "spaces.Room", on_delete=models.PROTECT, related_name="schedules"
    )
    section = models.ForeignKey(
        "timetable.Section", on_delete=models.PROTECT, related_name="schedules"
    )

    # > validation end_time should alway be bigger than start_time
    # ? need to check that there no overlap. may need to store duration
    # and implement a non overlap function like for semester and terms.
    def clean(self) -> None:
        """Check that the date are correct"""
        if self.end_time is not None:
            if self.start_time:
                assert (
                    self.start_time < self.end_time
                ), "start_time must be before end_time"

    def __str__(self):
        return f"{self.section}: {self.get_weekday_display()} {self.start_time}–{self.end_time}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["weekday", "room", "start_time"],
                name="uniq_slot_per_room",
            )
        ]
        indexes = [
            models.Index(fields=["weekday", "room", "start_time"]),
        ]
