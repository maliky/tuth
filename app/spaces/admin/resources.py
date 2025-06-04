"""Resources module."""

from import_export import fields, resources
from app.spaces.models import Room, Building

from .widgets import BuildingWidget


class RoomResource(resources.ModelResource):
    # ? we need this be we import from a short_name only and not the int id field of
    # building
    building = fields.Field(
        column_name="building",
        attribute="building",
        widget=BuildingWidget(model=Building, field="short_name"),
    )

    class Meta:
        model = Room
        # fields are (in order): building, code, standard_capacity, exam_capacity
