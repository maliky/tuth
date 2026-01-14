"""Core Admin module for academics."""

from typing import TypeAlias, cast

from django import forms
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
    CurriculumCourseFacultyFilterAC,
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
from django.utils.text import Truncator

ModelChoiceFieldT: TypeAlias = forms.ModelChoiceField | forms.ModelMultipleChoiceField


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
        # "faculty_count_link",
        # "course_count_link",
        # "curriculum_count_link",
        # "department_chair_links",
        # "student_counts_by_level_link"
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
        qs = obj.departments.all().order_by("shortname")
        rows = []
        for dept in qs:
            url = reverse("admin:academics_department_changelist") + (
                f"?college__id__exact={obj.id}&id__exact={dept.id}"
            )
            rows.append((url, dept.code))
        if not rows:
            return ""
        return format_html_join(", ", '<a href="{}">{}</a>', rows)

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
        "curricula_links",
    )
    autocomplete_fields = ("curricula",)
    # > TODO: Add the list of student enrolled in this course the current semester.
    inlines = [RequiresInline, PrerequisiteInline, CourseCurriculumInline]
    list_select_related = ("department",)
    # list_editable = ("department",)
    list_filter = (DepartmentFilterAC, CurriculumFilterAC, CourseCollegeFilter)

    list_per_page = 100
    list_max_show_all = 500

    search_fields = ("short_code", "department__code", "title")
    fields = ("short_code", "department", "number", "title", "description")
    actions = [update_department, merge_courses_action]

    def get_queryset(self, request):
        """Prefetch curricula for link rendering in list_display."""
        qs = super().get_queryset(request)
        qs = qs.prefetch_related("curricula")
        curriculum_id = request.GET.get("in_curriculum_courses__curriculum")
        if curriculum_id:
            try:
                curriculum_id = int(curriculum_id)
            except (TypeError, ValueError):
                return qs
            return qs.filter(curricula__id=curriculum_id)
        return qs

    def lookup_allowed(self, lookup, value, request=None):
        """Allow legacy curriculum lookup for course filters."""
        if lookup == "in_curriculum_courses__curriculum":
            return True
        return super().lookup_allowed(lookup, value, request)

    @admin.display(description="Curricula")
    def curricula_links(self, obj: Course):
        """Link each curriculum name to its admin change page."""
        rows = [
            (reverse("admin:academics_curriculum_change", args=[cur.pk]), cur.short_name)
            for cur in obj.curricula.all().order_by("short_name")
        ]
        if not rows:
            return "-"
        return format_html_join(", ", '<a href="{}">{}</a>', rows)

    def get_form(self, request, obj=None, **kwargs):
        """Return the admin form with dep ordered by their shortname."""
        form = super().get_form(request, obj, **kwargs)
        department_field = form.base_fields.get("department")

        if isinstance(
            department_field,
            (forms.ModelChoiceField, forms.ModelMultipleChoiceField),
        ):
            # Mypy: cast to model choice fields before ordering the queryset.
            department_field = cast(ModelChoiceFieldT, department_field)
            if department_field.queryset is not None:
                # Mypy: ensure queryset is set before chaining queryset methods.
                department_field.queryset = department_field.queryset.select_related(
                    "college"
                ).order_by("college__code", "shortname")
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
        "course_count_link",
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

    @admin.display(description="Courses")
    def course_count_link(self, obj):
        """Link course counts to the course changelist for this curriculum."""
        count = obj.course_count()
        url = reverse("admin:academics_course_changelist") + f"?curricula={obj.id}"
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
        "course_display",
        "department_link",
        "curriculum",
        "section_count_link",
        "faculty_links",
    )
    # list_editable = ("curriculum",)
    list_filter = (
        "curriculum__college",
        CurriculumFilterAC,
        DepartmentFilterAC,
        CurriculumCourseFacultyFilterAC,
    )

    autocomplete_fields = ("curriculum", "course")
    list_select_related = ("curriculum", "course")
    search_fields = ("curriculum__short_name", "course__code")
    list_per_page = 100
    list_max_show_all = 500

    # Optional inline to list all curricula for this curriculum_course.
    # inlines = [CurriculumCourseInline]

    ordering = ("course__short_code",)
    actions = [update_curriculum]

    def get_queryset(self, request):
        """Annotate section totals and prefetch faculty for list_display."""
        qs = super().get_queryset(request)
        return (
            qs.select_related("course__department")
            .prefetch_related("sections__faculty__staff_profile__user")
            .annotate(section_total=Count("sections", distinct=True))
        )

    @admin.display(description="Course")
    def course_display(self, obj: CurriculumCourse) -> str:
        """Truncate course display to avoid very long values in list view."""
        return Truncator(str(obj.course)).chars(50)

    @admin.display(description="Department")
    def department_link(self, obj: CurriculumCourse):
        """Link to departments filtered to this course's department."""
        dept = getattr(obj.course, "department", None)
        if not dept:
            return "-"
        url = reverse("admin:academics_course_changelist") + (f"?department={dept.id}")
        return format_html('<a href="{}">{}</a>', url, dept.code)

    @admin.display(description="Sections", ordering="section_total")
    def section_count_link(self, obj):
        """Link to sections filtered by this curriculum course."""
        count = getattr(obj, "section_total", None)
        if count is None:
            count = obj.sections.count()
        url = reverse("admin:timetable_section_changelist") + (
            f"?curriculum_course__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description="Faculty")
    def faculty_links(self, obj):
        """List linked faculty teaching sections for this curriculum course."""
        faculties = []
        seen = set()
        for section in obj.sections.all():
            faculty = section.faculty
            if not faculty or faculty.pk in seen:
                continue
            seen.add(faculty.pk)
            faculties.append(
                (
                    reverse("admin:people_faculty_change", args=[faculty.pk]),
                    faculty.staff_profile.long_name,
                )
            )
        if not faculties:
            return "-"
        return format_html_join(", ", '<a href="{}">{}</a>', faculties)


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
    list_display = (
        "code",
        "long_name",
        "college",
        "course_count_link",
        "faculty_count_link",
    )
    list_filter = [
        "college",
    ]
    list_editable = ("college",)
    search_fields = ("code", "long_name", "college")
    inlines = [DepartmentCourseInline]
    actions = ["merge_departments_action"]

    def get_queryset(self, request):
        # > explain the djangonic logic here
        qs = super().get_queryset(request)
        return qs.annotate(
            course_count=Count("courses", distinct=True),
            faculty_total=Count(
                "courses__in_curriculum_courses__sections__faculty", distinct=True
            ),
        )

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

    @admin.display(description="Teaching Faculty", ordering="faculty_total")
    def faculty_count_link(self, obj):
        """Link to faculty teaching sections in this department."""
        count = getattr(obj, "faculty_total", None)
        if count is None:
            count = (
                obj.courses.filter(in_curriculum_courses__sections__faculty__isnull=False)
                .values_list("in_curriculum_courses__sections__faculty_id", flat=True)
                .distinct()
                .count()
            )
        url = reverse("admin:people_faculty_changelist") + (
            f"?section__curriculum_course__course__department={obj.id}"
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
