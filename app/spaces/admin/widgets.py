"""Widgets module."""

from import_export import widgets

from app.shared.utils import CachedWidgetMixin

from app.spaces.models.core import Room, Space


class SpaceWidget(CachedWidgetMixin, widgets.ForeignKeyWidget):

    def __init__(self):
        super().__init__(Space, field="code")

    def clean(
        self,
        value: str | None,
        row: dict[str, str] | None = None,
        *args,
        **kwargs,
    ) -> Space | None:
        """Return an optional Space identified by code.

        if it does not exists, creates it.
        """

        if not value:
            return None

        key = value.strip().upper()
        if key in self._cache:
            return self._cache[key]

        space, _ = Space.objects.get_or_create(
            code=key,
            defaults={"full_name": value.strip()},
        )
        self._cache[key] = space
        return space

    def after_import(self, dataset, result, **kwargs):
        super().after_import(dataset, result, **kwargs)


class RoomWidget(CachedWidgetMixin, widgets.ForeignKeyWidget):
    """Resolve or create a :class:Room using room_code and space."""

    def __init__(self):
        super().__init__(Room, field="code")
        self.space_w = SpaceWidget()

    def clean(
        self,
        value: str,
        row: dict[str, str] | None = None,
        *args,
        **kwargs,
    ) -> Room | None:
        """Using the room no, and the space code, returns a Room (eventualy)."""

        room_code = value.strip()

        space_code = (row or {}).get("space", "").strip()
        space = self.space_w.clean(value=space_code, row=row)

        room_space = space or Space.get_tba_space()
        key = (room_space.pk, room_code or "TBA")
        if key in self._cache:
            return self._cache[key]

        room, _ = Room.objects.get_or_create(
            space=room_space,
            code=room_code or "TBA",
        )

        self._cache[key] = room
        return room

    def after_import(self, dataset, result, **kwargs):
        super().after_import(dataset, result, **kwargs)
        self.space_w.after_import(dataset, result, **kwargs)


class RoomCodeWidget(CachedWidgetMixin, widgets.ForeignKeyWidget):
    """Create a :class:Room from values like "AA-01"."""

    def __init__(self):
        super().__init__(Room, field="code")
        self.space_w = SpaceWidget()

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

        key = (getattr(space, "pk", None), room_code)
        if key in self._cache:
            return self._cache[key]

        room, _ = Room.objects.get_or_create(
            space=space,
            code=room_code,
        )
        self._cache[key] = room

        return room

    def after_import(self, dataset, result, **kwargs):
        super().after_import(dataset, result, **kwargs)
        self.space_w.after_import(dataset, result, **kwargs)

    def render(self, room, obj=None):
        """Transform a room object in a string for export."""
        return f"{room.space.code}-{room.code}" if room else ""
