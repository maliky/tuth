"""Core Admin module for academics."""

from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Count
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.academics.models import (
    College,
    Course,
    Curriculum,
    CurriculumCourse,
    CurriculumStatus,
    Department,
    Major,
    MajorCurriculumCourse,
    Minor,
    MinorCurriculumCourse,
    Prerequisite,
)
from app.people.models.student import Student
from app.shared.admin.filters import BaseCollegeFilter
from app.shared.admin.mixins import CollegeRestrictedAdmin, DepartmentRestrictedAdmin

from .actions import update_curriculum, update_department
from .filters import (
    CourseCollegeFilter,
    CurriculumFilterAC,
    DepartmentFilterAC,
)
from .inlines import (
    CourseCurriculumInline,
    CurriculumCourseInline,
    DepartmentCourseInline,
    PrerequisiteInline,
    RequiresInline,
)
from .merges import (
    merge_courses_action,
    merge_curricula,
    merge_curricula_action,
    merge_departments,
    merge_departments_action,
)
from .resources import (
    CollegeResource,
    CourseResource,
    CurriculumCourseResource,
    CurriculumResource,
    DepartmentResource,
    PrerequisiteResource,
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
        "faculty_count_link",
        "course_count_link",
        "curriculum_count_link",
        "department_chair_links",
        "student_counts_by_level_link",
    )
    search_fields = ("code", "long_name")

    @admin.display(description="Curricula")
    def curriculum_count_link(self, obj: College):
        count = obj.curricula.count()
        url = reverse("admin:academics_curriculum_changelist") + (
            f"?college__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description="Faculty")
    def faculty_count_link(self, obj: College):
        count = obj.faculty_count
        url = reverse("admin:people_faculty_changelist") + (
            f"?college__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description="Courses")
    def course_count_link(self, obj: College):
        count = obj.course_count
        url = reverse("admin:academics_course_changelist") + (
            f"?department__college__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description="Departments")
    def department_chair_links(self, obj: College):
        """Link departments filtered by college."""
        qs = obj.departments.all().order_by("short_name")
        rows = []
        for dept in qs:
            url = reverse("admin:academics_department_changelist") + (
                f"?college__id__exact={obj.id}&id__exact={dept.id}"
            )
            rows.append((url, dept.short_name))
        if not rows:
            return ""
        return format_html_join(", ", '<a href="{}">{}</a>', rows)

    @admin.display(description="Students by level")
    def student_counts_by_level_link(self, obj: College):
        """Link to students filtered by college and computed level."""
        rows = []
        students = list(Student.objects.filter(curriculum__college=obj))
        for level in ("Freshman", "Sophomore", "Junior", "Senior"):
            count = sum(1 for s in students if getattr(s, "class_level", "") == level)
            url = reverse("admin:people_student_changelist") + (
                f"?curriculum__college__id__exact={obj.id}&class_level={level}"
            )
            rows.append((url, level, count))
        return format_html_join(" | ", '<a href="{}">{}</a>: {}', rows)

    @admin.display(description="Active curricula")
    def active_curricula_list(self, obj: College):
        if not getattr(obj, "pk", None):
            return "Save the college to view curricula."
        active = obj.curricula.filter(is_active=True).order_by("short_name")
        rows = [
            (
                reverse("admin:academics_curriculum_change", args=[cur.pk]),
                cur.short_name,
            )
            for cur in active
        ]
        if not rows:
            return "None"
        return format_html_join(", ", '<a href="{}">{}</a>', rows)

    @admin.display(description="Inactive curricula")
    def inactive_curricula_list(self, obj: College):
        if not getattr(obj, "pk", None):
            return "Save the college to view curricula."
        inactive = obj.curricula.filter(is_active=False).order_by("short_name")
        rows = [
            (
                reverse("admin:academics_curriculum_change", args=[cur.pk]),
                cur.short_name,
            )
            for cur in inactive
        ]
        if not rows:
            return "None"
        return format_html_join(", ", '<a href="{}">{}</a>', rows)

    fields = ("code", "long_name", "active_curricula_list", "inactive_curricula_list")
    readonly_fields = ("active_curricula_list", "inactive_curricula_list")


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
        "list_curricula_str",
    )
    autocomplete_fields = ("curricula",)
    # > TODO: Add the list of student enrolled in this course the current semester.
    inlines = [RequiresInline, PrerequisiteInline, CourseCurriculumInline]
    list_select_related = ("department",)
    list_editable = ("department",)
    list_filter = (CourseCollegeFilter, DepartmentFilterAC)

    list_per_page = 100
    list_max_show_all = 500

    search_fields = ("short_code", "department__short_name", "title")
    fields = ("short_code", "department", "number", "title", "description")
    actions = [update_department, merge_courses_action]

    def get_form(self, request, obj=None, **kwargs):
        """Return the admin form with dep ordered by their short_name."""
        form = super().get_form(request, obj, **kwargs)
        department_field = form.base_fields.get("department")

        if department_field is not None:
            department_field.queryset = department_field.queryset.select_related(
                "college"
            ).order_by("college__code", "short_name")
        return form


@admin.register(Major)
class MajorAdmin(admin.ModelAdmin):
    """Admin options for Major."""

    list_display = ("name", "course_count")


@admin.register(Minor)
class MinorAdmin(admin.ModelAdmin):
    """Admin options for Minor."""

    list_display = ("name", "course_count")


@admin.register(MajorCurriculumCourse)
class MajorCurriculumAdmin(admin.ModelAdmin):
    """Admin options for MajorCurriculumCourse."""

    list_display = ("major", "curriculum_course")


@admin.register(MinorCurriculumCourse)
class MinorCurriculumCourseAdmin(admin.ModelAdmin):
    """Admin options for MinorCurriculumCourse."""

    list_display = ("minor", "curriculum_course")


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
    list_display = (
        "short_name",
        "long_name",
        "college",
        "is_active",
        "status",
        "course_count",
        "student_count",
    )
    list_filter = ("college",)
    list_editable = ("status", "is_active", "college")
    autocomplete_fields = ("college",)
    inlines = [CurriculumCourseInline]

    # list_selected_relate reduces the number of queries in db
    list_select_related = ("college",)
    search_fields = ("short_name", "long_name")
    actions = ["merge_curricula_action"]

    def student_count(self, obj):
        """Adding a link to the student number."""
        count = obj.student_count()
        url = reverse("admin:people_student_changelist") + (
            f"?curriculum__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)


@admin.register(CurriculumCourse)
class CurriculumCourseAdmin(CollegeRestrictedAdmin):
    """Admin screen for :class:~app.academics.models.CurriculumCourse.

    list_display shows the curriculum and related course while
    autocomplete_fields make lookups faster. list_select_related joins
    both relations for efficient queries.
    """

    resource_class = CurriculumCourseResource
    college_field = "curriculum__college"
    list_display = (
        "course",
        "course__short_code",
        "curriculum",
        "course__department",
    )
    list_editable = ("curriculum",)
    list_filter = ("curriculum__college", CurriculumFilterAC, DepartmentFilterAC)

    autocomplete_fields = ("curriculum", "course")
    list_select_related = ("curriculum", "course")
    search_fields = ("curriculum__short_name", "course__code")
    list_per_page = 100
    list_max_show_all = 500

    # Optional inline to list all curricula for this curriculum_course.
    # inlines = [CurriculumCourseInline]

    ordering = ("course__short_code",)
    actions = [update_curriculum]


@admin.register(CurriculumStatus)
class CurriculumStatusAdmin(admin.ModelAdmin):
    """Lookup admin for CurriculumStatus."""

    search_fields = ("code", "label")
    list_display = ("code", "label")


@admin.register(Department)
class DepartmentAdmin(CollegeRestrictedAdmin):
    """Admin interface for :class:~app.academics.models.Department.

    Shows department code, name and college. autocomplete_fields speeds up
    college selection when editing a department.
    """

    resource_class = DepartmentResource
    list_display = ("short_name", "long_name", "college", "course_count_link")
    list_filter = [
        "college",
    ]
    list_editable = ("college",)
    search_fields = ("short_name", "long_name", "college")
    inlines = [DepartmentCourseInline]
    actions = ["merge_departments_action"]

    def get_queryset(self, request):
        # > explain the djangonic logic here
        qs = super().get_queryset(request)
        return qs.annotate(course_count=Count("courses", distinct=True))

    @admin.display(description="Courses", ordering="course_count")
    def course_count_link(self, obj):
        """Adding a link to the course number."""
        count = getattr(obj, "course_count", None)
        if count is None:
            count = obj.courses.count()
        url = reverse("admin:academics_course_changelist") + (
            f"?department__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)


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

    # search_fields = ("course", "prerequisite_course") # not permitted no search of fk
    list_display = ("course", "prerequisite_course", "curriculum")
    autocomplete_fields = ("course", "prerequisite_course", "curriculum")
    list_filter = (CurriculumFilterAC,)
    # search_fields = ("course", "prerequisite_course", "curriculum")
