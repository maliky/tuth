# app/admin/spaces_admin.py
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from .resources import BuildingResource, RoomResource
from app.models import Building, Room


@admin.register(Building)
class BuildingAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = BuildingResource
    list_display = ("short_name", "full_name")
    search_fields = ("short_name", "full_name")


@admin.register(Room)
class RoomAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = RoomResource
    list_display = ("name", "building", "standard_capacity", "exam_capacity")
    search_fields = ("name", "building__short_name", "building__full_name")
    autocomplete_fields = ("building",)
