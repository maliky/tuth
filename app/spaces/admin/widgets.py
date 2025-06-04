"""Widgets module."""

from import_export import widgets

from app.spaces.models import Building, Room


class BuildingWidget(widgets.ForeignKeyWidget):
    """
    Accept a building *short_name*.
    If it exists, return the Building instance;
    otherwise create a shell Building row on the fly.
    """

    def clean(self, value, row=None, *args, **kwargs) -> Building | None:
        if not value:
            return None

        building, _ = Building.objects.get_or_create(
            short_name=value,
            defaults={"full_name": value},
        )
        return building


class RoomWidget(widgets.ForeignKeyWidget):
    """
    Parse a Building-Room token and return the :class:`Room`.
    Resolve "B1-101" strings into Room objects and building
    """

    def clean(self, value, row=None, *args, **kwargs) -> Room | None:
        if not value:
            return None

        bcode, _, rcode = [v.strip() for v in value.partition("-")]

        bw = BuildingWidget(model=Building, field="short_name")
        building = bw.clean(value, row, *args, **kwargs)

        if not rcode:
            return None

        room, _ = Room.objects.get_or_create(name=rcode, building=building)
        return room
