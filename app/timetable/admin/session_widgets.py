"""timetable.admin.widgets.session module."""

from import_export import widgets

from app.shared.utils import get_in_row, parse_str
from app.spaces.admin.widgets import RoomCodeWgt
from app.timetable.choices import WEEKDAYS_NUMBER
from app.timetable.models.schedule import Schedule
from app.timetable.models.session import SecSession


class SecSessionWgt(widgets.ForeignKeyWidget):
    """Create a :class:SecSession from room and section."""

    def __init__(self):
        super().__init__(SecSession)  # va exporter session.pk
        self.room_w = RoomCodeWgt()
        self.schedule_w = ScheduleWgt()

    def clean(self, value, row=None, *args, **kwargs) -> SecSession | None:
        """Value should be the room?"""
        if not value:
            return None

        # location is a code such as AA-12
        location = get_in_row("location", row)
        room = self.room_w.clean(location, row=row)
        weekday_value = get_in_row("weekday", row)

        schedule = self.schedule_w.clean(value=weekday_value, row=row)

        # > This will break, I need a section id to create a secsession no?
        session, _ = SecSession.objects.get_or_create(
            room=room,
            schedule=schedule,
        )
        return session


class ScheduleWgt(widgets.ForeignKeyWidget):
    """Return a :class:Schedule based on weekday and times."""

    def __init__(self):
        super().__init__(Schedule)
        self.weekday_w = WeekdayWgt()

    def clean(self, value, row=None, *args, **kwargs) -> Schedule | None:
        """Return an existing Schedule using data from the import row."""

        weekday = self.weekday_w.clean(value)

        if weekday is None:
            return None

        start_time = get_in_row("start_time", row)
        end_time = get_in_row("end_time", row)

        schedule, _ = Schedule.objects.get_or_create(
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
        )

        return schedule


class WeekdayWgt(widgets.IntegerWidget):
    """Accept either the integer 1-7 or the English weekday name."""

    def clean(self, value, row=None, *args, **kwargs) -> int | None:
        """Accept either the integer 1-7 or the English weekday name."""
        day_val = parse_str(value, "lower", dft="")

        if not day_val:
            return WEEKDAYS_NUMBER.TBA

        if day_val.isdigit():
            return int(day_val)

        _map = {label.lower(): num for num, label in WEEKDAYS_NUMBER.choices}
        return _map[day_val]
