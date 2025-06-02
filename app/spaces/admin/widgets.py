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
<<<<<<< HEAD
    """Return or create a :class: `Room` from ``value``."""
=======
    """Parse a Building-Room token and return the :class:`Room`."""
>>>>>>> github/codo/add-roomwidget-class-and-tests

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None

<<<<<<< HEAD
        building_code, room_code = value.partition("-")
        building_code = building_code.strip()
        room_code = room_code.strip()
=======
        parts = str(value).split("-", 1)
        building_code = parts[0].strip()
>>>>>>> github/codo/add-roomwidget-class-and-tests

        building, _ = Building.objects.get_or_create(
            short_name=building_code,
            defaults={"full_name": building_code},
        )

<<<<<<< HEAD
        if not room_code:
            return None

        room, _ = Room.objects.get_or_create(name=room_code, building=building)
=======
        if len(parts) == 1 or not parts[1].strip():
            return None

        room_name = parts[1].strip()

        room, _ = Room.objects.get_or_create(
            name=room_name,
            building=building,
        )
>>>>>>> github/codo/add-roomwidget-class-and-tests
        return room
