"""Widgets module."""

from import_export import widgets

from app.spaces.models import Building, Room


class BuildingWidget(widgets.ForeignKeyWidget):
    """
    Accept a building *short_name*.
    If it exists, return the Building instance;
    otherwise create a shell Building row on the fly.
    """

    def clean(self, value, row=None, *args, **kwargs):
        if not value:  # blank cell → keep NULL FK
            return None
        obj, _created = Building.objects.get_or_create(
            short_name=value,
            defaults={"full_name": value},  # or leave blank / supply something smarter
        )
        return obj


class RoomWidget(widgets.ForeignKeyWidget):
    """Parse a Building-Room token and return the :class:`Room`.
    Resolve "B1-101" strings into Room objects."""

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None

        building_code, room_code = value.partition("-")
        building_code = building_code.strip()
        room_code = room_code.strip()

        building, _ = Building.objects.get_or_create(
            short_name=building_code,
            defaults={"full_name": building_code},
        )

        if not room_code:
            return None

        room, _ = Room.objects.get_or_create(name=room_code, building=building)
        token = value.strip()

        if "-" not in token:
            Building.objects.get_or_create(short_name=token)
            return None

        building_code, room_name = token.split("-", 1)
        building, _ = Building.objects.get_or_create(short_name=building_code)
        room, _ = Room.objects.get_or_create(name=room_name, building=building)
        return room
