"""Schedule module."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from django.db import models, transaction

from app.timetable.choices import WEEKDAYS_NUMBER


class Schedule(models.Model):
    """Weekday/Time slot definition used by session objects.

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

    def __str__(self):
        """Return weekday: start-end for quick inspection in admin."""
        # can we shorten weekday to only have the first 3 char?
        return f"{self.weekday_str}: {self.start_time_str}-{self.end_time_str}"

    @property
    def weekday_name(self) -> str:
        """Return the human‐readable name of this schedule’s weekday.

        e.g. "Monday", "Tuesday", etc.
        """
        return self.get_weekday_display()

    @property
    def weekday_str(self):
        """Return the str version of the day_no."""
        return WEEKDAYS_NUMBER(self.weekday).label

    @property
    def start_time_str(self) -> str:
        """Start time formatted as HH:MM."""
        return self.start_time.strftime("%H:%M")

    @property
    def end_time_str(self) -> str:
        """End time formatted as HH:MM or empty string."""
        return self.end_time.strftime("%H:%M") if self.end_time else ""

    def _find_next_free_slot(self, weekday) -> time:
        """Find a free time slot at the begining of the day.

        Scan in 1-minute steps from 01:00.
        find a (weekday, start_time) combination that doesn't exist yet.
        """
        # Anchor at 0 AM the 1/01/2009, what we look at is the time.
        cursor = datetime.combine(self.REF_DATE, time(0, 0))
        step = timedelta(minutes=1)

        # get the 1 minutes slots
        nb_slots_hours = int(3600 / step.seconds)

        # wrap in a transaction so concurrent saves won’t collide
        with transaction.atomic():
            # We cap it to avoid infinit loop.
            for _ in range(24 * nb_slots_hours):
                t = cursor.time()
                exists = Schedule.objects.filter(
                    weekday=weekday,
                    start_time=t,
                ).exists()
                if not exists:
                    return t
                cursor += step

        raise RuntimeError(f"Could not find a free 1-minute slot on {self.weekday}")

    # > validation end_time should alway be bigger than start_time
    # ? need to check that there no overlap. may need to store duration
    # and implement a non overlap function like for semester and terms.
    def clean(self) -> None:
        """Check that the date are correct."""
        if self.end_time is not None:
            assert self.start_time < self.end_time, "start_time must be before end_time"

    def save(self, *args, **kwargs):
        """Check and save the Schedule.

        1) ensure we always have a weekday.
        2) if no start_time, find the first free 5-minute slot >= 01:00
        """
        if self.weekday is None:
            self.weekday = WEEKDAYS_NUMBER.TBA  # type: ignore[unreachable]

        if self.start_time is None:
            self.start_time = self._find_next_free_slot(self.weekday)  # type: ignore[unreachable]

        super().save(*args, **kwargs)

    def is_set(self):
        """Returns True when the schedule is fully set."""
        weekday_set = self.weekday is not None and self.weekday != WEEKDAYS_NUMBER.TBA

        # we suppose that all unassigned time are before the ref_dat_start_time
        start_time_set = self.start_time < self.REF_TIME
        end_time_set = self.start_time is not None

        return weekday_set and start_time_set and end_time_set

    @classmethod
    def get_default(cls, new_schedule=False):
        """Return a default schedule.

        If new schedule is True we return the a new schedule on TBA Day
        """
        tba_day = WEEKDAYS_NUMBER.TBA
        if new_schedule:
            start_time = cls._find_next_free_slot(tba_day)
        else:
            start_time = cls.REF_TIME

        def_schedule, _ = cls.get_or_create(weekday=tba_day, start_time=start_time)

        return def_schedule

    class Meta:
        ordering = ["weekday", "start_time", "end_time"]
