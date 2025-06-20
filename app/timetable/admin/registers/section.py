"""app.timetable.admin.registers.section module."""

from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.timetable.admin.inlines import ReservationInline, SessionInline
from app.timetable.admin.resources.section import SectionResource
from app.timetable.models.section import Section


@admin.register(Section)
class SectionAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for :class:~app.timetable.models.Section.

    list_display includes semester, course and faculty information while
    inlines manage reservations and sessions. Filtering by curriculum is
    available through list_filter.
    """

    # ! TODO ajouter à la list, les rooms occupé et le nombre de sessions, le nombre de crédits
    resource_class = SectionResource
    list_display = ("semester", "course", "number", "faculty", "available_seats")
    inlines = [ReservationInline, SessionInline]
    list_filter = ("course__curricula",)
    autocomplete_fields = ("course", "semester", "faculty")

    # When Django pulls a Section list, it will join these related tables to reduce queries:
    list_select_related = (
        "course",
        "semester",
        "faculty",
    )

    search_fields = (
        "^course__code",  # fast starts-with on indexed code
        "faculty__long_name",  # or __first_name / __last_name
    )

    def get_queryset(self, request):
        """Returns something to make it faster.  But what is not clear.

        Prefetch all the Session → Room relationships:
        """
        # ! Need explaination on this get_queryset(request)
        # ! What is in request ?
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
