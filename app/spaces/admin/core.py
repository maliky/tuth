from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.space.admin import RoomResource
from app.spaces import Building, Room


@admin.register(Building)
class BuildingAdmin(GuardedModelAdmin):
    list_display = ("short_name", "full_name")
    search_fields = ("short_name", "full_name")


@admin.register(Room)
class RoomAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = RoomResource
    list_display = ("name", "building__short_name", "standard_capacity", "exam_capacity")
    search_fields = ("name", "building__short_name")
    autocomplete_fields = ("building",)
