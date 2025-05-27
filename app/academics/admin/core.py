from app.academics.admin.actions import update_curriculum, update_college
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
from .forms import BulkActionImportForm, CourseForm
from .filters import CurriculumFilter


@admin.register(Course)
class CourseAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = CourseResource
    list_display = ("code", "title", "credit_hours", "college")
    list_filter = ("curricula__college", "curricula")
    autocomplete_fields = ("curricula", "college")
    inlines = [SectionInline, PrerequisiteInline, RequiresInline]
    list_select_related = ("college",)
    actions = [update_college]

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
    actions = [update_curriculum]
    list_display = ("course", "prerequisite_course", "curriculum")
    autocomplete_fields = ("course", "prerequisite_course", "curriculum")
    list_filter = (CurriculumFilter,)
    search_field = ("course", "prerequisite_course", "curriculum")


@admin.register(Curriculum)
class CurriculumAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = CurriculumResource
    # add the action button on the import form
    import_form_class = BulkActionImportForm
    list_display = ("short_name", "title", "college")
    list_filter = ("college", "is_active")
    autocomplete_fields = ("college",)
    inlines = [CurriculumCourseInline]
    # list_selected_relate reduce the number of queries in db
    list_select_related = ("college",)
    search_fields = (
        "short_name",
        "title",
    )


@admin.register(College)
class CollegeAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_class = CollegeResource
    list_display = ("code", "fullname", "current_dean")
    search_fields = ("code", "fullname")
