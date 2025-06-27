"""app.timetable.admin.registers.section module."""

from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.people.models.staffs import Faculty
from app.registry.admin.inlines import GradeInline
from app.timetable.admin.inlines import SessionInline
from app.timetable.admin.resources.section import SectionResource
from app.timetable.models.section import Section


@admin.register(Section)
class SectionAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for Section.

    list_display includes semester, course and faculty information while
    inlines manage sessions. Filtering by curriculum is available through list_filter.
    """

    # ! TODO ajouter à la list, les rooms occupé et le nombre de sessions, le nombre de crédits
    resource_class = SectionResource
    list_display = ("semester", "program", "number", "faculty", "available_seats")
    inlines = [SessionInline, GradeInline]
    list_filter = ("program__curriculum",)
    autocomplete_fields = ("semester", "faculty")

    # Join related tables to reduce queries when pulling sections.
    list_select_related = ("program", "semester", "faculty")

    search_fields = ("^program__course__code",)  # fast starts-with on indexed code

    def get_queryset(self, request):
        """Prefetch all the Session -> Room relationships."""
        qs = super().get_queryset(request)
        return qs.prefetch_related("sessions__room")

    @admin.display(description="Sessions")
    def all_sessions(self, obj: Section) -> str:
        """Return a human-readable summary of this Section’s sessions.

        For example: “Mon 09:00–10:00 (Rm 101); Wed 09:00–10:00 (Rm 101)”
        """
        slots = []
        for sess in obj.sessions.all():
            slots.append(f"{sess.schedule} ({sess.room})")

        return "; ".join(slots) or "--"
