"""Wgts module."""

from import_export import widgets

from app.shared.utils import get_in_row, parse_str
from app.spaces.models.core import Room, Space


class SpaceWgt(widgets.ForeignKeyWidget):
    def __init__(self):
        super().__init__(Space, field="code")

    def clean(
        self,
        value: str | None,
        row: dict[str, str] | None = None,
        *args,
        **kwargs,
    ) -> Space:
        """Return an optional Space identified by code.

        If it does not exists, creates it.
        If nothing is passed return the default Space.
        """
        space_val = parse_str(value)
        if not space_val:
            return Space.get_dft()

        space, _ = Space.objects.get_or_create(
            code=space_val,
            defaults={"full_name": space_val},
        )
        return space


class RoomWgt(widgets.ForeignKeyWidget):
    """Resolve or create a :class:Room using room_code and space."""

    def __init__(self):
        super().__init__(Room, field="code")
        self.space_w = SpaceWgt()

    def clean(
        self,
        value: str,
        row: dict[str, str] | None = None,
        *args,
        **kwargs,
    ) -> Room:
        """Using the room no, and the space code, returns a Room (eventualy)."""
        room_code = parse_str(value)
        space_code = get_in_row("space", row) or "<TBA>"
        space = self.space_w.clean(value=space_code, row=row)

        room, _ = Room.objects.get_or_create(
            code=room_code or "<TBA>",
            space=space or Space.get_dft(),
        )
        return room


class RoomCodeWgt(widgets.ForeignKeyWidget):
    """Create a :class:Room from values like "AA-01"."""

    def __init__(self):
        super().__init__(Room, field="code")
        self.space_w = SpaceWgt()

    def clean(
        self,
        value: str | None,
        row: dict[str, str] | None = None,
        *args,
        **kwargs,
    ) -> Room | None:
        """Using the room code returns the Room.

        The room code should include the space code as AA-102.
        """
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
        """Transform a room object in a string for export."""
        return f"{room.space.code}-{room.code}" if room else ""
