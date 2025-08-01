"""app.timetable.admin.registers.section module."""

from django.contrib import admin

from app.people.models.staffs import Faculty
from app.registry.admin.inlines import GradeInline
from app.shared.admin.mixins import CollegeRestrictedAdmin
from app.timetable.admin.filters import SectionSemesterFilterAc
from app.timetable.admin.inlines import SecSessionInline
from app.timetable.admin.resources.section import SectionResource
from app.timetable.models.section import Section


@admin.register(Section)
class SectionAdmin(CollegeRestrictedAdmin):
    """Admin interface for Section.

    list_display includes semester, course and faculty information while
    inlines manage sessions and grade.
    Filtering by curriculum is available through list_filter.
    """

    resource_class = SectionResource
    college_field = "program__curriculum__college"
    list_display = (
        "program",
        "number",
        "semester",
        "faculty",
        "available_seats",
        "space_codes",
        "session_count",
        "credit_hours",
        "program__curriculum",
    )
    inlines = [SecSessionInline, GradeInline]
    list_filter = [
        SectionSemesterFilterAc
    ]  # , CurriBySemFilterAc]  #("program__curriculum",)
    autocomplete_fields = (
        "semester",
        "faculty",
    )

    # Join related tables to reduce queries when pulling sections.
    list_select_related = ("program", "semester", "faculty")

    search_fields = ("^program__course__short_code",)  # fast starts-with on indexed code

    def get_queryset(self, request):
        """Prefetch sessions and limit sections to the current faculty."""
        qs = super().get_queryset(request).prefetch_related("sessions__room")
        if request.user.is_superuser:
            return qs
        try:
            faculty = request.user.staff.faculty
        except (AttributeError, Faculty.DoesNotExist):
            return qs.none()
        return qs.filter(faculty=faculty)

    @admin.display(description="SecSessions")
    def all_sessions(self, obj: Section) -> str:
        """Return a human-readable summary of this Section’s sessions.

        For example: “Mon 09:00–10:00 (Rm 101); Wed 09:00–10:00 (Rm 101)”
        """
        slots = []
        for sess in obj.sessions.all():
            slots.append(f"{sess.schedule} ({sess.room})")

        return "; ".join(slots) or "--"

    @admin.display(description="# SecSessions")
    def session_count(self, obj: Section) -> int:
        """Return the number of sessions attached to this section."""
        return obj.sessions.count()

    @admin.display(description="Credits")
    def credit_hours(self, obj: Section) -> int:
        """Return credit hours for this section's program."""
        return obj.program.credit_hours
