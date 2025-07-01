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
    list_display = ("code", "full_name", "current_sections")

    def current_sections(self, obj):
        """Return sections scheduled in this space for the current semester."""
        from app.timetable.models.section import Section
        from app.timetable.utils import get_current_semester

        semester = get_current_semester()
        if semester is None:
            return "--"
        sections = (
            Section.objects.filter(
                semester=semester, sessions__room__space=obj
            )
            .distinct()
            .order_by("program__course__code", "number")
        )
        codes = [s.short_code for s in sections]
        return ", ".join(codes) if codes else "--"


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
