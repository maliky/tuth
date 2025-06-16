"""Import/export resources for timetable models. (Session)"""

from import_export import fields, resources
from import_export.widgets import TimeWidget

from app.spaces.admin.widgets import RoomWidget
from app.timetable.admin.widgets import WeekdayWidget
from app.timetable.admin.widgets.section import SectionWidget
from app.timetable.admin.widgets.session import ScheduleWidget
from app.timetable.models.session import Schedule, Session


class ScheduleResource(resources.ModelResource):
    weekday = fields.Field(
        column_name="weekday",
        attribute="weekday",
        widget=WeekdayWidget(),
    )
    start_time = fields.Field(
        column_name="start_time",
        attribute="start_time",
        widget=TimeWidget(format="%H:%M"),
    )
    end_time = fields.Field(
        column_name="end_time",
        attribute="end_time",
        widget=TimeWidget(format="%H:%M"),
    )

    class Meta:
        model = Schedule
        fields = ("weekday", "start_time", "end_time")
        import_id_fields = ("weekday", "start_time", "end_time")


class SessionResource(resources.ModelResource):
    room = fields.Field(
        column_name="room",
        attribute="room",
        widget=RoomWidget(),
    )
    schedule = fields.Field(
        column_name="weekday", attribute="schedule", widget=ScheduleWidget()
    )
    section = fields.Field(
        column_name="section_no",
        attribute="section",
        widget=SectionWidget(),
    )

    class Meta:
        model = Session
        import_id_fields = ("room", "schedule", "section")
        fields = ("room", "schedule", "section")
