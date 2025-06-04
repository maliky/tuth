"""Core module."""

# app/admin/academic_admin.py
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from app.timetable.models import AcademicYear, Semester, Section
from .inlines import ScheduleInline, SemesterInline, ReservationInline
from .resources import SectionResource, SemesterResource


@admin.register(AcademicYear)
class AcademicYearAdmin(GuardedModelAdmin):
    list_display = ("long_name", "start_date", "short_name")
    date_hierarchy = "start_date"
    inlines = [SemesterInline]
    ordering = ("-start_date",)
    search_fields = ("short_name",)


@admin.register(Semester)
class SemesterAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = SemesterResource
    list_filter = ("academic_year",)  # needs academic_year her
    autocomplete_fields = ("academic_year",)
    search_fields = ("number",)


@admin.register(Section)
class SectionAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = SectionResource
    list_display = ("long_code", "course", "semester", "faculty", "max_seats")
    inlines = [ReservationInline, ScheduleInline]
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

    # If you want to prefetch all the Schedule → Room relationships:
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("schedules__location")

    @admin.display(description="Schedules")
    def all_schedules(self, obj: Section) -> str:
        """
        Return a human-readable summary of this Section’s schedules.
        For example: “Mon 09:00–10:00 (Rm 101); Wed 09:00–10:00 (Rm 101)”
        """
        slots = []
        for sched in obj.schedules.all():
            day = sched.get_weekday_display()  # “Monday”, “Tuesday”, etc.
            st = sched.start_time.strftime("%H:%M") if sched.start_time else ""
            et = sched.end_time.strftime("%H:%M") if sched.end_time else ""
            room = sched.location or ""
            slots.append(f"{day} {st}–{et} ({room})")
        return "; ".join(slots) or "—"
