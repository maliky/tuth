"""Core module."""

from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.academics.admin.actions import update_college, update_curriculum
from app.academics.models import College, Course, Curriculum, Prerequisite
from app.academics.models.curriculum_course import CurriculumCourse
from app.timetable.admin.inlines import SectionInline

from .filters import CurriculumFilter
from .forms import BulkActionImportForm, CourseForm
from .inlines import (
    CurriculumCourseInline,
    PrerequisiteInline,
    RequiresInline,
)
from .resources import (
    CollegeResource,
    CourseResource,
    CurriculumCourseResource,
    CurriculumResource,
    PrerequisiteResource,
)


@admin.register(Course)
class CourseAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface configuration for :class:`~app.academics.models.Course`."""

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
    """Admin interface for :class:`~app.academics.models.Prerequisite`."""

    resource_class = PrerequisiteResource
    actions = [update_curriculum]
    list_display = ("course", "prerequisite_course", "curriculum")
    autocomplete_fields = ("course", "prerequisite_course", "curriculum")
    list_filter = (CurriculumFilter,)
    search_field = ("course", "prerequisite_course", "curriculum")


@admin.register(Curriculum)
class CurriculumAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin options for :class:`~app.academics.models.Curriculum`."""

    resource_class = CurriculumResource
    # add the action button on the import form
    import_form_class = BulkActionImportForm
    list_display = ("short_name", "long_name", "college")
    list_filter = ("college", "is_active")
    autocomplete_fields = ("college",)
    inlines = [CurriculumCourseInline]
    # list_selected_relate reduce the number of queries in db
    list_select_related = ("college",)
    search_fields = ("short_name", "long_name")


@admin.register(College)
class CollegeAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for :class:`~app.academics.models.College`."""

    resource_class = CollegeResource
    list_display = ("code", "long_name")
    search_fields = ("code", "long_name")


@admin.register(CurriculumCourse)
class CurriculumCourseAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin screen for :class:`~app.academics.models.CurriculumCourse`."""

    resource_class = CurriculumCourseResource
    list_display = ("curriculum", "course")
    autocomplete_fields = ("curriculum", "course")
    list_select_related = ("curriculum", "course")
