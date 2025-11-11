"""spaces.Resources module."""

from import_export import fields, resources

from app.spaces.admin.widgets import SpaceWidget
from app.spaces.models.core import Room


class RoomResource(resources.ModelResource):
    """Standard import-export resource for Room with associated Space."""

    code = fields.Field(attribute="code", column_name="room", default="TBA")
    space = fields.Field(
        column_name="space",
        attribute="space",
        widget=SpaceWidget(),
    )
    standard_capacity = fields.Field(column_name="standard_capacity")
    exam_capacity = fields.Field(column_name="exam_capacity")

    class Meta:
        model = Room
        import_id_fields = ("space", "code")
        fields = ("space", "code", "standard_capacity", "exam_capacity")
        skip_unchanged = True
