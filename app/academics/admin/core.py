"""Core Admin module for academics."""

from typing import Iterable, TypeAlias, cast, no_type_check

from django import forms
from django.contrib import admin, messages
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.academics.models.curriculum_course import CurriculumCourse
from app.academics.models import (
    College,
    Course,
    Curriculum,
    CurriculumStatus,
    Department,
    Prerequisite,
)
from app.people.models.student import Student
from app.shared.admin.filters import BaseCollegeFilter
from app.shared.admin.mixins import CollegeRestrictedAdmin, DepartmentRestrictedAdmin
from app.people.admin.mixins import MergeWizardMixin, ModelT

from .actions import update_curriculum, update_department
from .filters import (
    CourseCollegeFilter,
    CourseCurriculumFilter,
    CurriculumFilterAC,
    CurriculumCourseFacultyFilterAC,
    DepartmentCurriculumFilterAC,
    DepartmentFilterAC,
)
from .inlines import (
    CourseCurriculumInline,
    CourseFeeInline,
    CurriculumCourseInline,
    CurriculumCourseFeeInline,
    DepartmentCourseInline,
    PrerequisiteInline,
    RequiresInline,
)
from .merges import (
    merge_courses_action,
    merge_courses_by_short_code_action,
    merge_curricula,
    merge_departments,
    merge_curriculum_courses,
)
from app.academics.prereq_graph import export_prereq_graph
from .resources import (
    CollegeResource,
    CourseResource,
    CurriculumCourseResource,
    CurriculumResource,
    DepartmentResource,
    PrerequisiteResource,
)
from django.utils.text import Truncator
from django.conf import settings
from app.timetable.admin.filters import SemesterFilterAC

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
        "grade_count",
    )
    # Curricula column removed from list_display; keep helper for reuse elsewhere.
    # Use list filters for curricula to avoid reverse M2M autocomplete errors.
    # > TODO: Add the list of student enrolled in this course the current semester.
    inlines = [
        CourseFeeInline,
        RequiresInline,
        PrerequisiteInline,
        CourseCurriculumInline,
    ]
    list_select_related = ("department",)
    list_editable = ("department",)
    list_filter = (
        SemesterFilterAC,
        DepartmentFilterAC,
        CourseCurriculumFilter,
        CourseCollegeFilter,
    )

    list_per_page = 100
    list_max_show_all = 500

    search_fields = ("short_code", "department__code", "title")
    fields = ("short_code", "department", "number", "title", "description")
    # Actions include manual merge and short_code-based merge helpers.
    actions = [
        update_department,
        merge_courses_action,
        merge_courses_by_short_code_action,
    ]

    def get_queryset(self, request):
        """Prefetch curricula for link rendering in list_display."""
        qs = super().get_queryset(request)
        qs = qs.prefetch_related("curricula").annotate(
            grade_total=Count("in_curriculum_courses__sections__grade", distinct=True)
        )
        curriculum_id = request.GET.get("curricula__id__exact") or request.GET.get(
            "in_curriculum_courses__curriculum"
        )
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

    @admin.display(description="Grades", ordering="grade_total")
    def grade_count(self, obj: Course) -> int:
        """Return the number of grades recorded for this course."""
        return int(getattr(obj, "grade_total", 0) or 0)

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


@admin.register(Curriculum)
class CurriculumAdmin(MergeWizardMixin, CollegeRestrictedAdmin):
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
    list_filter = (SemesterFilterAC, "college")
    list_editable = ("status", "is_active", "college")
    autocomplete_fields = ("college",)
    inlines = [CurriculumCourseInline]

    # list_selected_relate reduces the number of queries in db
    list_select_related = ("college",)
    search_fields = ("short_name", "long_name")
    # Keep short_name out of the wizard to avoid active-name uniqueness collisions.
    merge_fields = ("long_name", "college", "status", "is_active", "description")
    actions = ["export_prereq_graph_action"]

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
        url = reverse("admin:academics_course_changelist") + (
            f"?curricula__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.action(description="Export prerequisite graph (JSON/JS + DOT + PNG)")
    def export_prereq_graph_action(self, request, queryset):
        """Export prerequisite graphs for selected curricula."""
        if not queryset:
            self.message_user(request, "No curricula selected.", level=messages.WARNING)
            return

        outputs = []
        for curriculum in queryset:
            try:
                outputs.append(export_prereq_graph(curriculum))
            except Exception as exc:  # pragma: no cover - admin message path
                self.message_user(
                    request,
                    f"Failed for {curriculum.short_name}: {exc}",
                    level=messages.ERROR,
                )
                continue

        if not outputs:
            return

        links = []
        for output in outputs:
            slug = output.json_path.stem
            view_url = reverse("academics_prereq_graph", args=[slug])
            png_url = f"{settings.MEDIA_URL}Prereq/{output.png_path.name}"
            links.append(
                format_html(
                    '<a href="{view}">{label}</a> (<a href="{png}">PNG</a>)',
                    view=view_url,
                    png=png_url,
                    label=f"View graph {slug}",
                )
            )
        msg = format_html_join(" · ", "{}", ((link,) for link in links))
        self.message_user(
            request,
            format_html("Generated prerequisite graphs: {}.", msg),
            level=messages.SUCCESS,
        )

    def merge_records(self, target: ModelT, sources: Iterable[ModelT]) -> dict[str, int]:
        """Merge curricula using the shared merge helper."""
        target_curriculum = cast(Curriculum, target)
        source_curricula = cast(Iterable[Curriculum], sources)
        request = getattr(self, "_merge_request", None)
        self._warn_curriculum_merge_precheck(
            request,
            target_curriculum,
            source_curricula,
        )
        summary = merge_curricula(target_curriculum, source_curricula)
        if request and summary.get("curricula_retained", 0):
            self.message_user(
                request,
                (
                    "Some source curricula were retained due to invoice conflicts. "
                    "Review scripts/curriculum_merge_conflicts.sql before retrying."
                ),
                level=messages.WARNING,
            )
        return {
            "merged": summary.get("curricula_merged", 0),
            "sections_merged": summary.get("sections_merged", 0),
            "skipped_invoices": summary.get("skipped_invoices", 0),
            "credit_hours_conflicts": summary.get("credit_hours_conflicts", 0),
            "is_required_conflicts": summary.get("is_required_conflicts", 0),
            "is_elective_conflicts": summary.get("is_elective_conflicts", 0),
        }

    # Avoid mypy internal error on the nested curriculum overlap query.
    @no_type_check
    def _warn_curriculum_merge_precheck(
        self,
        request,
        target: Curriculum,
        sources: Iterable[Curriculum],
    ) -> None:
        """Warn when the pre-merge SQL check should be reviewed."""
        if request is None:
            return
        source_ids = [cur.pk for cur in sources if cur.pk]
        if not source_ids or not target.pk:
            return
        overlap_count = CurriculumCourse.objects.filter(
            curriculum=target,
            course_id__in=CurriculumCourse.objects.filter(
                curriculum_id__in=source_ids
            ).values("course_id"),
        ).count()
        if overlap_count:
            self.message_user(
                request,
                (
                    "Course overlaps detected; run "
                    "scripts/curriculum_merge_conflicts.sql before merging."
                ),
                level=messages.WARNING,
            )


@admin.register(CurriculumCourse)
class CurriculumCourseAdmin(MergeWizardMixin, CollegeRestrictedAdmin):
    """Admin screen for :class:~app.academics.models.CurriculumCourse.

    list_display shows the curriculum and related course while
    autocomplete_fields make lookups faster. list_select_related joins
    both relations for efficient queries.
    """

    resource_class = CurriculumCourseResource
    college_field = "curriculum__college"
    merge_fields = (
        "curriculum",
        "course",
        "credit_hours",
        "is_required",
        "is_elective",
    )
    list_display = (
        "course_display",
        "department_link",
        "curriculum",
        "level_number",
        "section_count_link",
        "faculties_links",
    )
    list_filter = (
        SemesterFilterAC,
        "curriculum__college",
        CurriculumFilterAC,
        DepartmentFilterAC,
        CurriculumCourseFacultyFilterAC,
    )

    list_editable = ("curriculum",)
    autocomplete_fields = ("curriculum", "course")
    list_select_related = ("curriculum", "course")
    # Include short_code to support curriculum course autocomplete lookups.
    search_fields = ("curriculum__short_name", "course__code", "course__short_code")
    list_per_page = 100
    list_max_show_all = 500

    # Optional inline to list all curricula for this curriculum_course.
    # inlines = [CurriculumCourseInline]
    inlines = [CurriculumCourseFeeInline]

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

    def merge_object_label(self, obj) -> str:
        """Return a label for merge choices."""
        curriculum_course = cast(CurriculumCourse, obj)
        course = curriculum_course.course
        curriculum = curriculum_course.curriculum
        course_label = course.short_code or course.code or str(course)
        curriculum_label = curriculum.short_name or curriculum.long_name
        return f"{curriculum_label} | {course_label}"

    def merge_records(self, target, sources):
        """Merge curriculum courses into the target selection."""
        target_course = cast(CurriculumCourse, target)
        return merge_curriculum_courses(target_course, sources)

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
        return format_html('<a href="{}">{}</a>', url, dept.shortname)

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

    @admin.display(description="Faculties")
    def faculties_links(self, obj):
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
class DepartmentAdmin(MergeWizardMixin, CollegeRestrictedAdmin):
    """Admin interface for :class:~app.academics.models.Department.

    Shows department code, name and college. autocomplete_fields speeds up
    college selection when editing a department.
    """

    resource_class = DepartmentResource
    merge_fields = ("code", "long_name", "college")
    list_display = (
        "code",
        "long_name",
        "college",
        "course_count_link",
        "faculty_count_link",
    )
    list_filter = [
        "college",
        DepartmentCurriculumFilterAC,
    ]
    list_editable = ("college",)
    search_fields = ("code", "long_name", "college")
    inlines = [DepartmentCourseInline]

    def get_queryset(self, request):
        # > explain the djangonic logic here
        qs = super().get_queryset(request)
        return qs.annotate(
            course_count=Count("courses", distinct=True),
            faculty_total=Count(
                "courses__in_curriculum_courses__sections__faculty", distinct=True
            ),
        ).prefetch_related("courses__curricula")

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

    # > Curricula list removed from list_display to reduce page load.

    def merge_records(self, target: ModelT, sources: Iterable[ModelT]) -> dict[str, int]:
        """Merge departments using the shared merge helper."""
        target_department = cast(Department, target)
        source_departments = cast(Iterable[Department], sources)
        summary = merge_departments(target_department, source_departments)
        return {"merged": summary.get("merged", 0)}

    def merge_records_action(self, request, queryset):
        """Warn about college alignment before showing the merge form."""
        response = super().merge_records_action(request, queryset)
        if request.method == "POST" and request.POST.get("apply_merge"):
            return response
        messages.warning(
            request,
            (
                "Review the selected departments carefully. "
                "Departments should belong to the same college before merging."
            ),
        )
        return response


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
