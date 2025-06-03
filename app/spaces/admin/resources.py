"""Resources module."""

from import_export import fields, resources
from app.spaces.models import Room, Building

from .widgets import BuildingWidget


class RoomResource(resources.ModelResource):
    building = fields.Field(
        column_name="building",
        attribute="building",
        widget=BuildingWidget(model=Building, field="short_name"),
    )

    class Meta:
        model = Room
        import_id_fields = ("name", "building")
        fields = ("name", "building")
