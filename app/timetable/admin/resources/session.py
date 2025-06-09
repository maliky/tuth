from import_export import fields, resources

from app.spaces.admin.widgets import RoomWidget
from app.timetable.admin.widgets import WeekdayWidget
from app.timetable.admin.widgets.section import SectionWidget
from app.timetable.models.session import Session


class SessionResource(resources.ModelResource):
    room = fields.Field(
        column_name="room",
        attribute="room",
        widget=RoomWidget(),
    )
    schedule = fields.Field(
        column_name="weekday",
        attribute="schedule",
        widget=WeekdayWidget(),
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
