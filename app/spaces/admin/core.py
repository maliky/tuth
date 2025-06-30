"""Core module."""

from app.timetable.admin.inlines import SessionInline
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from .resources import RoomResource
from app.spaces.models import Space, Room


@admin.register(Space)
class SpaceAdmin(GuardedModelAdmin):
    """Admin management for :class:~app.spaces.models.Space.

    Exposes basic listing and search over the space code and name.
    """

    search_fields = ("code", "full_name")
    list_display = ("code", "full_name")

    # > list the sections in that building for the current semester


@admin.register(Room)
class RoomAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin configuration for :class:~app.spaces.models.Room.

    list_display shows the room code and capacities. Sessions are edited via
    SessionInline. The full_code field is read‑only and the space
    relation uses autocomplete.
    """

    resource_class = RoomResource
    fields = (
        "code",
        "standard_capacity",
        "exam_capacity",
        "space",
    )
    list_display = ("code", "space", "standard_capacity", "exam_capacity")
    list_filter = ("space",)
    search_fields = ("space__code", "code")
    autocomplete_fields = ["space"]
    inlines = [SessionInline]
