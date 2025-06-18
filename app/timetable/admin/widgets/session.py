"""timetable.admin.widgets.session module"""

from import_export import widgets

from app.shared.enums import WEEKDAYS_NUMBER
from app.spaces.admin.widgets import RoomCodeWidget
from app.timetable.models.session import Schedule, Session


class SessionWidget(widgets.ForeignKeyWidget):
    """Create a :class:`Session` from room and schedule data."""

    def __init__(self):
        super().__init__(Session)  # va exporter session.pk
        self.room_w = RoomCodeWidget()
        self.schedule_w = ScheduleWidget()

    def clean(self, value, row=None, *args, **kwargs) -> Session | None:
        "value should be the room?"
        if not value:
            return None

        room = self.room_w.clean(value.strip(), row)

        weekday_value = row.get("weekday", "").strip()
        schedule = self.schedule_w.clean(value=weekday_value, row=row)

        session, _ = Session.objects.get_or_create(
            room=room,
            schedule=schedule,
        )
        return session


class ScheduleWidget(widgets.ForeignKeyWidget):
    """Return a :class:`Schedule` based on weekday and times."""

    def __init__(self):
        super().__init__(Schedule)
        self.weekday_w = WeekdayWidget

    def clean(self, value, row=None, *args, **kwargs) -> Schedule | None:
        """
        We get the weekday but start and end time should be present in row
        """

        weekday: int | None = self.weekday_w().clean(value=value)
        if weekday is None:
            return None

        start_time = row.get("start_time", "").strip()
        end_time = row.get("end_time", "").strip()

        schedule, _ = Schedule.objects.get_or_create(
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
        )

        return schedule


class WeekdayWidget(widgets.IntegerWidget):
    """Accept either the integer 1-7 or the English weekday name."""

    def clean(self, value, row=None, *args, **kwargs) -> int | None:
        if not value:
            return None

        token = str(value).strip().lower()

        if token.isdigit():
            return int(token)

        _map = {label.lower(): num for num, label in WEEKDAYS_NUMBER.choices}
        assert token in _map, f"{token} is not in {_map}"

        return _map[token]
