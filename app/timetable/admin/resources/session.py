from import_export import fields, resources

from app.spaces.admin.widgets import RoomWidget
from app.timetable.admin.widgets import WeekdayWidget
from app.timetable.models.session import Session


class SessionResource(resources.ModelResource):
    room = fields.Field(
        column_name="location",
        attribute="room",
        widget=RoomWidget(),
    )
    schedule = fields.Field(
        column_name="weekday",
        attribute="weekday",
        widget=WeekdayWidget(),
    )

    class Meta:
        model = Session
        import_id_fields = ("room", "schedule")
        fields = ("room", "schedule")
