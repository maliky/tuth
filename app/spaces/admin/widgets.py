from import_export import widgets

from app.spaces.models import Building


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
