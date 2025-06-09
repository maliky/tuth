"""Widgets module."""

from import_export import widgets

from app.spaces.models import Space
from app.spaces.models.core import Room


class SpaceWidget(widgets.ForeignKeyWidget):
    """
    Accept a space *code*.
    If it exists, return the Space instance;
    otherwise create a Space on the fly.
    """

    def __init__(self):
        super().__init__(Space, field="core")

    def clean(self, value, row=None, *args, **kwargs):

        if not value:
            return None

        space, _ = Space.objects.get_or_create(
            code=value.strip(),
            defaults={"full_name": value.strip()},
        )
        return space


class RoomWidget(widgets.ForeignKeyWidget):
    """
    Parse a value with the room_code.  Check the row for a space.
    """

    def __init__(self):
        super().__init__(Room, field="code")
        self.space_w = SpaceWidget()

    def clean(self, value, row=None, *args, **kwargs) -> Space | None:
        if not value:
            return None

        room_code = value.strip()

        assert "space" in row, f"'space' column not found in {row.keys()}"
        space_code = row.get("space", "").strip()
        space = self.space_w.clean(value=space_code, row=row)

        room, _ = Room.objects.get_or_create(
            space=space,
            code=room_code,
        )

        return room


class RoomCodeWidget(widgets.ForeignKeyWidget):
    """
    Parse CSV field like "AA-01" or "SAPEC-SAPEC".
    Auto-create Space and Room instances.
    """

    def __init__(self):
        super().__init__(Room, field="code")
        self.space_w = SpaceWidget()

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None

        space_code, _, room_code = [v.strip() for v in value.partition("-")]
        space = self.space_w.clean(value=space_code, row=row)

        room, _ = Room.objects.get_or_create(
            space=space,
            code=room_code,
        )

        return room

    def render(self, room, obj=None):
        return f"{room.space.code}-{room.code}" if room else ""
