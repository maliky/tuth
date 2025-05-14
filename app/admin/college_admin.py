# app/admin/college_admin.py
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.models import College, Course, Curriculum, Prerequisite

from .inlines import PrerequisiteInline, RequiresInline, SectionInline
from .resources import CourseResource, CurriculumResource, PrerequisiteResource


@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ("code", "fullname", "current_dean")
    search_fields = ("code", "fullname")


@admin.register(Curriculum)
class CurriculumAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = CurriculumResource
    list_display = ("title", "level", "academic_year", "college", "is_active")
    list_filter = ("college", "level", "academic_year", "is_active")
    autocomplete_fields = ("college", "academic_year")
    list_select_related = (
        "academic_year",
        "college",
    )


@admin.register(Course)
class CourseAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = CourseResource
    list_display = ("code", "title", "curriculum", "credit_hours")
    list_filter = ("curriculum__college", "curriculum__academic_year")
    autocomplete_fields = ("curriculum",)
    inlines = [SectionInline, PrerequisiteInline, RequiresInline]
    list_select_related = (
        "curriculum",
        "curriculum__college",
        "curriculum__academic_year",
    )


@admin.register(Prerequisite)
class PrerequisiteAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = PrerequisiteResource
    list_display = ("course", "prerequisite_course")
    autocomplete_fields = ("course", "prerequisite_course")
