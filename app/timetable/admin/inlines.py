"""app.timetable.Inlines modules."""

from django.contrib import admin
from django.db.models import Count

from app.timetable.models.section import Section
from app.timetable.models.semester import Semester
from app.timetable.models.session import SecSession


class SemesterInline(admin.TabularInline):
    """Inline for managing Semester rows."""

    model = Semester
    extra = 0
    max_num = 3
    fields = ("number", "start_date", "end_date")
    ordering = ("start_date",)


class SecSessionInline(admin.TabularInline):
    """Inline editor for SecSession rows."""

    model = SecSession
    extra = 0
    fields = (
        "section",
        "section_semester",
        "room",
        "schedule",
    )
    autocomplete_fields = (
        "section",
        "room",
        "schedule",
    )
    readonly_fields = ("section_semester",)

    @admin.display(description="Semester")
    def section_semester(self, obj):
        """Show the semester for the inline section reference."""
        if not obj.section_id:
            return "-"
        return obj.section.semester


class SectionInline(admin.TabularInline):
    """Inline for creating Section rows."""

    model = Section
    verbose_name_plural = "Sections taught"
    show_change_link = True
    extra = 0
    fields = (
        "curriculum_course",
        "semester",
        "number",
        "start_date",
        "max_seats",
        "current_registrations",
        "enrolled_total",
        "credit_hours",
    )
    readonly_fields = (
        # Read-only values keep the inline lightweight on faculty profiles.
        "curriculum_course",
        "semester",
        "current_registrations",
        "enrolled_total",
        "credit_hours",
    )
    ordering = ("-semester__start_date", "-number")

    def get_queryset(self, request):
        """Annotate the inline queryset with enrollment totals."""
        qs = super().get_queryset(request)
        return qs.select_related(
            "semester",
            "faculty__staff_profile__user",
            "curriculum_course__credit_hours",
            "curriculum_course__course__department",
            "curriculum_course__curriculum",
        ).annotate(enrolled_total=Count("section_registrations", distinct=True))

    @admin.display(description="Enrolled", ordering="enrolled_total")
    def enrolled_total(self, obj):
        """Return the number of registered students for this section."""
        return getattr(obj, "enrolled_total", 0)

    @admin.display(description="Credits")
    def credit_hours(self, obj):
        """Return credit hours for the related curriculum course."""
        return obj.curriculum_course.credit_hours_id or 0
