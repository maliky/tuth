# app/admin/academic_admin.py
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from app.models import AcademicYear, Term, Section
from .inlines import TermInline


@admin.register(AcademicYear)
class AcademicYearAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    list_display = ("long_name", "starting_date", "short_name")
    date_hierarchy = "starting_date"
    inlines = [TermInline]
    ordering = ("-starting_date",)
    search_fields = ("long_name", "short_name")


@admin.register(Term)
class TermAdmin(GuardedModelAdmin):
    list_display = ("__str__", "academic_year", "number", "start_date", "end_date")
    list_filter = ("academic_year", "number")
    autocomplete_fields = ("academic_year",)
    search_fields = ("academic_year__long_name", "number")


@admin.register(Section)
class SectionAdmin(GuardedModelAdmin):
    list_display = ("long_code", "course", "term", "instructor", "room", "max_seats")
    list_filter = ("term__academic_year", "term__number", "course__curriculum__college")
    autocomplete_fields = ("course", "term", "instructor", "room")
    list_select_related = (
        "course",
        "term",
        "term__academic_year",
        "instructor",
        "room",
        "course__curriculum",
    )
