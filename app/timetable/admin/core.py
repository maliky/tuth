# app/admin/academic_admin.py
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from app.timetable.models import AcademicYear, Semester, Section
from .inlines import SemesterInline
from .resources import SemesterResource


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
class SectionAdmin(GuardedModelAdmin):
    list_display = ("long_code", "course", "semester", "instructor", "room", "max_seats")
    list_filter = (
        "semester",
        "course__code",
        "course__curricula",
        "course__curricula__college",
        "instructor",
        "room",
    )
    autocomplete_fields = ("course", "semester", "instructor", "room")
    list_select_related = (
        "course",
        "semester",
        "instructor",
        "room",
    )

    search_fields = (
        "^course__code",  # fast starts-with on indexed code
        "instructor__username",  # or __first_name / __last_name
    )
