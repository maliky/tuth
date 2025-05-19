# app/admin/academic_admin.py
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from app.models import AcademicYear, Semester, Section
from .inlines import SemesterInline


@admin.register(AcademicYear)
class AcademicYearAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    list_display = ("long_name", "start_date", "short_name")
    date_hierarchy = "start_date"
    inlines = [SemesterInline]
    ordering = ("-start_date",)
    search_fields = ("long_name", "short_name")


@admin.register(Semester)
class SemesterAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    list_display = ("__str__", "academic_year", "number", "start_date", "end_date")
    list_filter = ("academic_year", "number")
    autocomplete_fields = ("academic_year",)
    search_fields = ("academic_year__long_name", "number")


@admin.register(Section)
class SectionAdmin(GuardedModelAdmin):
    list_display = ("long_code", "course", "semester", "instructor", "room", "max_seats")
    list_filter = ("semester", "course__curricula__college")
    autocomplete_fields = ("course", "semester", "instructor", "room")
    list_select_related = (
        "course",
        "semester",
        "instructor",
        "room",
    )
