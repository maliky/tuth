"""Core module."""

from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.academics.admin.actions import update_college, update_curriculum
from app.academics.models import (
    College,
    Course,
    Curriculum,
    Prerequisite,
    Department,
)
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
    DepartmentResource,
)


@admin.register(Course)
class CourseAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for :class:`~app.academics.models.Course`.

    Provides course management with extra tools:
    * ``list_display`` shows the code, title, credits and college fields.
    * ``list_filter`` allows filtering by curriculum.
    * ``inlines`` embed related sections and prerequisite relations.
    * ``actions`` exposes the ``update_college`` bulk action.

    Example:
        Select multiple courses and choose **Update college** from the actions
        dropdown to assign them all to a different college.
    """

    resource_class = CourseResource
    list_display = ("code", "title", "credit_hours", "college")
    list_filter = ("curricula",)
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
                    "departments",
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
    """Admin interface for :class:`~app.academics.models.Prerequisite`.

    Options configured:
    * ``list_display`` shows the course, the prerequisite and the curriculum.
    * ``list_filter`` uses :class:`CurriculumFilter` to narrow by curriculum.
    * ``actions`` provides ``update_curriculum`` for bulk updates.

    Example:
        On the prerequisites list page, select rows and run
        **Attach / update curriculum** to set a curriculum for them.
    """

    resource_class = PrerequisiteResource
    actions = [update_curriculum]
    list_display = ("course", "prerequisite_course", "curriculum")
    autocomplete_fields = ("course", "prerequisite_course", "curriculum")
    list_filter = (CurriculumFilter,)
    search_fields = ("course", "prerequisite_course", "curriculum")


@admin.register(Curriculum)
class CurriculumAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin options for :class:`~app.academics.models.Curriculum`.

    Key features:
    * Uses ``BulkActionImportForm`` for import/export with an extra action
      button.
    * ``inlines`` manage related curriculum courses inline.
    * ``list_display`` includes short and long names with the college.
    * ``list_filter`` allows filtering by college and active state.
    """

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
    """Admin settings for :class:`~app.academics.models.College`.

    Displays the college code and name and provides search capability on both
    fields via ``list_display`` and ``search_fields``.
    """

    resource_class = CollegeResource
    list_display = ("code", "long_name")
    search_fields = ("code", "long_name")


@admin.register(Department)
class DepartmentAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for :class:`~app.academics.models.Department`.

    Shows department code, name and college. ``autocomplete_fields`` speeds up
    college selection when editing a department.
    """

    resource_class = DepartmentResource
    list_display = ("code", "full_name", "college")
    search_fields = ("code", "full_name")
    autocomplete_fields = ("college",)


@admin.register(CurriculumCourse)
class CurriculumCourseAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin screen for :class:`~app.academics.models.CurriculumCourse`.

    ``list_display`` shows the curriculum and related course while
    ``autocomplete_fields`` make lookups faster. ``list_select_related`` joins
    both relations for efficient queries.
    """

    resource_class = CurriculumCourseResource
    list_display = ("curriculum", "course")
    autocomplete_fields = ("curriculum", "course")
    list_select_related = ("curriculum", "course")
    search_fields = ("curriculum__short_name", "course__code")
