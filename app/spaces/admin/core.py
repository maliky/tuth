"""Core module."""

from app.timetable.admin.inlines import SessionInline
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from .resources import RoomResource
from app.spaces.models import Space, Room


@admin.register(Space)
class SpaceAdmin(GuardedModelAdmin):
    """Admin management for :class:`~app.spaces.models.Space`."""

    search_fields = ("code", "full_name")
    list_display = ("code", "full_name")


@admin.register(Room)
class RoomAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin configuration for :class:`~app.spaces.models.Room`."""

    resource_class = RoomResource
    list_display = ("code", "space", "standard_capacity", "exam_capacity")
    search_fields = ("space__code", "code")
    autocomplete_fields = ["space"]
    inlines = [SessionInline]
