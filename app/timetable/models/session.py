"""Session module."""

from __future__ import annotations
from datetime import datetime, time, timedelta
from django.db import models, transaction
from django.forms import ValidationError

from app.shared.enums import WEEKDAYS_NUMBER


class Schedule(models.Model):
    """Time slot definition used by session objects.

    Example:
        >>> Schedule.objects.create(weekday=1, start_time=time(9, 0))
    """

    # a ref date for the time
    REF_DATE = datetime(2009, 9, 1)
    # a time of ref for the start of the day
    REF_TIME = time(8, 0)
    REF_DATETIME = REF_DATE + timedelta(hours=REF_TIME.hour)

    weekday = models.PositiveSmallIntegerField(
        choices=WEEKDAYS_NUMBER.choices,
        help_text="Week day number (Monday=1, Tuesday=2, …)",
    )
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)

    @property
    def weekday_name(self) -> str:
        """
        Return the human‐readable name of this schedule’s weekday,
        e.g. "Monday", "Tuesday", etc.
        """
        return self.get_weekday_display()

    @property
    def weekday_str(self):
        "return the str version of the day_no"
        return WEEKDAYS_NUMBER(self.weekday).label

    @property
    def start_time_str(self) -> str:
        """Start time formatted as ``HH:MM``."""
        return self.start_time.strftime("%H:%M")

    @property
    def end_time_str(self) -> str:
        """End time formatted as ``HH:MM`` or empty string."""
        return self.end_time.strftime("%H:%M") if self.end_time else ""

    def __str__(self):
        """Return ``weekday: start-end`` for quick inspection in admin."""
        # can we shorten weekday to only have the first 3 char?
        return f"{self.weekday_str}: {self.start_time_str}-{self.end_time_str}"

    def _find_next_free_slot(self) -> time:
        """
        Scan in 5-minute steps from 01:00 today until we
        find a (weekday, start_time) combination that doesn't exist yet.
        """
        # anchor at 0 AM today

        cursor = datetime.combine(self.REF_DATE, time(1, 0))
        step = timedelta(minutes=5)

        nb_slots_hours = int(3600 / step.seconds)  # should be 5

        # wrap in a transaction so concurrent saves won’t collide
        with transaction.atomic():
            # cap at from 0:00 to 6:00 hrs to avoid infinite loops
            # 12, 5min slots in on hour
            for _ in range(6 * nb_slots_hours):
                t = cursor.time()
                exists = Schedule.objects.filter(
                    weekday=self.weekday,
                    start_time=t,
                ).exists()
                if not exists:
                    return t
                cursor += step

        raise RuntimeError(
            "Could not find a free 5-minute slot on {self.weekday}. -> no Schedule"
        )

    # > validation end_time should alway be bigger than start_time
    # ? need to check that there no overlap. may need to store duration
    # and implement a non overlap function like for semester and terms.
    def clean(self) -> None:
        """Check that the date are correct"""
        if self.end_time is not None:
            assert self.start_time < self.end_time, "start_time must be before end_time"

    def save(self, *args, **kwargs):
        """
        # 1) ensure we always have a weekday
        # 2) if no start_time, find the first free 5-minute slot >= 01:00
        """
        if self.weekday is None:
            self.weekday = WEEKDAYS_NUMBER.TBA  # type: ignore[unreachable]

        if self.start_time is None:
            self.start_time = self._find_next_free_slot()  # type: ignore[unreachable]

        super().save(*args, **kwargs)

    def is_set(self):
        """Returns True when the schedule is fully set."""
        weekday_set = self.weekday is not None and self.weekday != WEEKDAYS_NUMBER.TBA

        # we suppose that all unassigned time are before the ref_dat_start_time
        start_time_set = self.start_time < self.REF_TIME
        end_time_set = self.start_time is not None

        return weekday_set and start_time_set and end_time_set

    class Meta:
        ordering = ["weekday", "start_time", "end_time"]


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
        """Return ``Schedule, Room`` for use in admin lists."""
        return f"{self.schedule}, {self.room}"

    def schedule_is_set(self):
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
