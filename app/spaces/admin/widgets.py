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
    """Parse a Building-Room token and return the :class:`Room`."""

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None

        parts = str(value).split("-", 1)
        building_code = parts[0].strip()

        building, _ = Building.objects.get_or_create(
            short_name=building_code,
            defaults={"full_name": building_code},
        )

        if len(parts) == 1 or not parts[1].strip():
            return None

        room_name = parts[1].strip()

        room, _ = Room.objects.get_or_create(
            name=room_name,
            building=building,
        )
        return room
