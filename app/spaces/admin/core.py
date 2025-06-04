"""Core module."""

from app.timetable.admin.inlines import ScheduleInline
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from .resources import RoomResource
from app.spaces.models import Building, Room


@admin.register(Building)
class BuildingAdmin(GuardedModelAdmin):
    search_fields = ("short_name", "full_name")
    list_display = ("short_name", "full_name")


@admin.register(Room)
class RoomAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = RoomResource
    list_display = ("name", "building", "standard_capacity", "exam_capacity")
    search_fields = ("building__short_name", "name")
    autocomplete_fields = ["building"]
    inlines = [ScheduleInline]
