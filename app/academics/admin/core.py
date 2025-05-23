from app.timetable.admin.inlines import SectionInline
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.academics.models import College, Course, Curriculum, Prerequisite

from .inlines import (
    PrerequisiteInline,
    RequiresInline,
    CurriculumCourseInline,
)
from .resources import (
    CourseResource,
    CurriculumResource,
    PrerequisiteResource,
    CollegeResource,
)
from .forms import CourseForm
from .filters import CurriculumFilter


@admin.register(Course)
class CourseAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = CourseResource
    list_display = ("code", "title", "credit_hours", "college")
    list_filter = ("curricula__college", "curricula")
    autocomplete_fields = ("curricula", "college")
    inlines = [SectionInline, PrerequisiteInline, RequiresInline]
    list_select_related = ("college",)

    search_fields = ("code", "curricula__short_name", "sections__number")
    form = CourseForm
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "number",
                    "title",
                    "credit_hours",
                    "college",
                    "curricula",
                )
            },
        ),
        (
            "Additional details",
            {
                "classes": ("collapse",),
                "fields": ("description",),
            },
        ),
    )


@admin.register(Prerequisite)
class PrerequisiteAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = PrerequisiteResource
    list_display = ("course", "prerequisite_course", "curriculum")
    autocomplete_fields = ("course", "prerequisite_course", "curriculum")
    list_filter = (CurriculumFilter,)
    search_field = ("course", "prerequisite_course", "curriculum")


@admin.register(Curriculum)
class CurriculumAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = CurriculumResource
    list_display = ("short_name", "college")
    list_filter = ("college", "short_name", "is_active")
    autocomplete_fields = ("college",)
    inlines = [CurriculumCourseInline]
    list_select_related = ("college",)
    search_fields = ("title",)


@admin.register(College)
class CollegeAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_class = CollegeResource
    list_display = ("code", "fullname", "current_dean")
    search_fields = ("code", "fullname")
