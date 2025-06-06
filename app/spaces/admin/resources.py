"""spaces.Resources module."""

from typing import Any
from import_export import fields, resources
from app.spaces.models import Space, Room

from .widgets import RoomWidget, SpaceWidget


class SpaceResource(resources.ModelResource):
    """Simple import-export resource for Space."""

    class Meta:
        model = Space
        import_id_fields = ("short_name",)
        fields = ("short_name", "full_name")
        skip_unchanged = True
        report_skipped = True


class RoomResource(resources.ModelResource):
    """Standard import-export resource for Room with associated Space."""

    space = fields.Field(
        column_name="space",
        attribute="space",
        widget=SpaceWidget(model=Space, field="short_name"),
    )

    code = fields.Field(
        column_name="room",
        attribute="code",
    )

    # ── add capacities if they’re in your CSV (optional) ────────────
    standard_capacity = fields.Field(column_name="standard_capacity")
    exam_capacity = fields.Field(column_name="exam_capacity")

    class Meta:
        model = Room
        import_id_fields = ("space", "code")
        fields = ("space", "code", "standard_capacity", "exam_capacity")
        skip_unchanged = True
        report_skipped = True
