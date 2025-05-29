# app/admin/academic_admin.py
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from app.timetable.models import AcademicYear, Semester, Section
from .inlines import SemesterInline
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
    list_display = ("long_code", "course", "semester", "faculty", "room", "max_seats")
    list_filter = (
        "semester",
        "course__code",
        "course__curricula",
        "course__curricula__college",
        "faculty",
        "room",
    )
    autocomplete_fields = ("course", "semester", "faculty", "room")
    list_select_related = (
        "course",
        "semester",
        "faculty",
        "room",
    )

    search_fields = (
        "^course__code",  # fast starts-with on indexed code
        "faculty__username",  # or __first_name / __last_name
    )
