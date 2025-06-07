"""Widgets module."""

from import_export import widgets

from app.spaces.models import Space
from app.spaces.models.core import Room


class SpaceWidget(widgets.ForeignKeyWidget):
    """
    Accept a space *short_name*.
    If it exists, return the Space instance;
    otherwise create a Space on the fly.
    """

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None

        space_name, _, _ = [v.strip() for v in value.partition("-")]
        space, _ = Space.objects.get_or_create(
            short_name=space_name,
            defaults={"full_name": space_name},
        )
        return space


class RoomWidget(widgets.ForeignKeyWidget):
    """
    Parse CSV field like "AA-01" or "SAPEC-SAPEC".
    Auto-create Space and Room instances.
    """

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None

        space_name, _, room_code = [v.strip() for v in value.partition("-")]

        space, _ = Space.objects.get_or_create(
            short_name=space_name,
            defaults={"full_name": space_name},
        )

        room, _ = Room.objects.get_or_create(
            space=space,
            code=room_code,
        )

        return room

    def render(self, value, obj=None):
        return f"{value.space.short_name}-{value.code}" if value else ""
