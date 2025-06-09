"""app.timetable.admin.registers.section module"""

from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.timetable.admin.inlines import ReservationInline, SessionInline
from app.timetable.admin.resources.section import SectionResource
from app.timetable.models.section import Section


@admin.register(Section)
class SectionAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for :class:`~app.timetable.models.Section`."""

    resource_class = SectionResource
    list_display = ("long_code", "course", "semester", "faculty", "max_seats")
    inlines = [ReservationInline, SessionInline]
    list_filter = (
        "semester",
        "course__curricula__college",
        "course__curricula",
        "course__code",
        "faculty",
    )
    autocomplete_fields = ("course", "semester", "faculty")

    # When Django pulls a Section list, it will join these related tables to reduce queries:
    list_select_related = (
        "course",
        "semester",
        "faculty",
    )

    search_fields = (
        "^course__code",  # fast starts-with on indexed code
        "faculty__full_name",  # or __first_name / __last_name
    )

    # If you want to prefetch all the Session → Room relationships:
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("sessions__room")

    @admin.display(description="Sessions")
    def all_sessions(self, obj: Section) -> str:
        """
        Return a human-readable summary of this Section’s sessions.
        For example: “Mon 09:00–10:00 (Rm 101); Wed 09:00–10:00 (Rm 101)”
        """
        slots = []
        for sched in obj.sessions.all():
            day = sched.get_weekday_display()  # “Monday”, “Tuesday”, etc.
            st = sched.start_time.strftime("%H:%M") if sched.start_time else ""
            et = sched.end_time.strftime("%H:%M") if sched.end_time else ""
            room = sched.room or ""
            slots.append(f"{day} {st}–{et} ({room})")
        return "; ".join(slots) or "—"
