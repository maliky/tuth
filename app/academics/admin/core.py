"""Core module."""

from django.urls import path

from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.academics.admin.actions import update_curriculum
from app.academics.admin.views import CurriculumBySemester
from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.academics.models.prerequisite import Prerequisite
from app.academics.models.program import Program
from app.shared.admin.mixins import CollegeRestrictedAdmin, DepartmentRestrictedAdmin

from .filters import CurriculumFilter
from .inlines import (
    CourseProgramInline,
    CurriculumProgramInline,
    PrerequisiteInline,
    RequiresInline,
)
from .resources import (
    CollegeResource,
    CourseResource,
    CurriculumResource,
    DepartmentResource,
    PrerequisiteResource,
    ProgramResource,
)


@admin.register(College)
class CollegeAdmin(SimpleHistoryAdmin, ImportExportModelAdmin, GuardedModelAdmin):
    """Admin settings for :class:~app.academics.models.College.

    Displays the college code and name and provides search capability on both
    fields via list_display and search_fields.
    """

    resource_class = CollegeResource
    list_display = (
        "code",
        "long_name",
        "faculty_count",
        "course_count",
        "curricula_names",
        "department_chairs",
        "student_counts_by_level",
    )
    search_fields = ("code", "long_name")


@admin.register(Course)
class CourseAdmin(DepartmentRestrictedAdmin):
    """Admin interface for Course.

    Provides course management with extra tools:
    - list_display shows the code, title, credits and college fields.
    - list_filter allows filtering by curriculum.
    - inlines embed related sections and prerequisite relations.
    - actions exposes the update_college bulk action.

    Example:
        Select multiple courses and choose Update college from the actions
        dropdown to assign them all to a different college.
    """

    resource_class = CourseResource
    list_display = (
        "short_code",
        "title",
        "department",
    )
    list_filter = ("department__college",)
    autocomplete_fields = ("curricula",)
    # > TODO: Add the list of student enrolled in this course the current semester.
    inlines = [PrerequisiteInline, RequiresInline, CourseProgramInline]
    list_select_related = ("department",)

    search_fields = ("short_code", "department__code", "title")
    fields = ("short_code", "department", "number", "title", "description")


@admin.register(Curriculum)
class CurriculumAdmin(CollegeRestrictedAdmin):
    """Admin options for Curriculum.

    Key features:
    - inlines manage related curriculum courses inline.
    - list_display includes short and long names with the college.
    - list_filter allows filtering by college and active state.
    """

    resource_class = CurriculumResource
    # add the action button on the import form
    list_display = ("short_name", "long_name", "college", "is_active", "status")
    list_filter = ("college",)
    autocomplete_fields = ("college",)
    inlines = [CurriculumProgramInline]

    # list_selected_relate reduces the number of queries in db
    list_select_related = ("college",)
    search_fields = ("short_name", "long_name")

    def get_urls(self):
        """Returns urls."""
        urls = super().get_urls()
        custom = [
            path(
                "curriculum_by_semester_ac/",
                self.admin_site.admin_view(
                    CurriculumBySemester.as_view(model_admin=self)
                ),
                name="curriculum_by_semester_ac",
            )
        ]
        return custom + urls


@admin.register(Department)
class DepartmentAdmin(CollegeRestrictedAdmin):
    """Admin interface for :class:~app.academics.models.Department.

    Shows department code, name and college. autocomplete_fields speeds up
    college selection when editing a department.
    """

    resource_class = DepartmentResource
    list_display = ("short_name", "long_name", "college")
    list_filter = ("college",)
    search_fields = ("short_name", "long_name", "college")


@admin.register(Prerequisite)
class PrerequisiteAdmin(SimpleHistoryAdmin, ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for :class:~app.academics.models.Prerequisite.

    Options configured:
    - list_display shows the course, the prerequisite and the curriculum.
    - list_filter uses :class:CurriculumFilter to narrow by curriculum.
    - actions provides update_curriculum for bulk updates.

    Example:
        On the prerequisites list page, select rows and run
        Attach / update curriculum to set a curriculum for them.
    """

    resource_class = PrerequisiteResource
    actions = [update_curriculum]
    list_display = ("course", "prerequisite_course", "curriculum")
    autocomplete_fields = ("course", "prerequisite_course", "curriculum")
    list_filter = (CurriculumFilter,)
    # search_fields = ("course", "prerequisite_course", "curriculum")


@admin.register(Program)
class ProgramAdmin(CollegeRestrictedAdmin):
    """Admin screen for :class:~app.academics.models.Program.

    list_display shows the curriculum and related course while
    autocomplete_fields make lookups faster. list_select_related joins
    both relations for efficient queries.
    """

    resource_class = ProgramResource
    college_field = "curriculum__college"
    list_display = ("course", "curriculum")
    # need to order the filter by curriculum_college
    list_filter = ("curriculum",)
    autocomplete_fields = ("curriculum", "course")
    list_select_related = ("curriculum", "course")
    search_fields = ("curriculum__short_name", "course__code")
    # inlines = [CourseProgramInline]
    # > Add the list all curriculum having this particular program, CurriculumInline
