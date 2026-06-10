"""Core Admin module for academics."""

from typing import Iterable, Literal, TypeAlias, cast, no_type_check

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.db import connection, transaction
from django.db.models import Count, IntegerField
from django.db.models.expressions import RawSQL
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from app.academics.models.curriculum_course import CurriCrs
from app.academics.models import (
    CurriStdEnroll,
    College,
    Course,
    Curriculum,
    CurriStatus,
    Department,
    Prerequisite,
)
from app.people.models.student import Student
from app.people.models.student_curriculum_enrollment import StdCurriEnroll
from app.finance.models.invoice import Invoice
from app.shared.admin.filters import BaseCollegeFlt
from app.shared.admin.mixins import (
    CollegeRestrictedAdmin,
    CollegeRestrictedNoHistoryAdmin,
    DptRestrictedAdmin,
    ProtectedDeleteAdminMixin,
)
from app.people.admin.mixins import MergeWizardMixin, ModelT

from .actions import (
    _apply_curri_relink,
    _notify_curri_relink_result,
    attach_fee_stacks,
    update_curri,
    update_curri_to_dpt_college_dft,
    update_dpt,
    update_level_number,
)
from .filters import (
    CrsCollegeFlt,
    CrsCurriFlt,
    CurriFltAC,
    CurriCrsFacultyFltAC,
    CurriCrsStdFltAC,
    DptCurriFltAC,
    DptFltAC,
)
from .inlines import (
    CrsCurriIL,
    CrsFeeStackIL,
    CurriCrsIL,
    DptCrsIL,
    PrerequisiteIL,
    RequiresIL,
)
from .merges import (
    MERGE_CHOICE_KEEP_SOURCE,
    MERGE_CHOICE_KEEP_TARGET,
    MERGE_CHOICE_MERGE,
    MERGE_CHOICE_SKIP,
    ConflictChoiceByCrsIdT,
    StdCurriRecordMergeSummaryT,
    empty_std_curri_record_summary,
    merge_crss_action,
    merge_crss_by_short_code_action,
    merge_curra,
    merge_dpts,
    merge_curri_crss,
    merge_std_enrollment_pair,
    list_curri_crs_conflicts,
)
from app.academics.prereq_graph import export_prereq_graph
from .resources import (
    CollegeResource,
    CrsResource,
    CurriCrsResource,
    CurriResource,
    DptResource,
    PrerequisiteResource,
)
from django.utils.text import Truncator
from django.conf import settings
from app.timetable.admin.filters import SemFltAC

ModelChoiceFieldT: TypeAlias = forms.ModelChoiceField | forms.ModelMultipleChoiceField
MergeFieldSourceChoiceT = Literal["target", "source"]


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
        # "crs_count_link",
        # "curri_count_link",
        # "dpt_chair_links",
        # "std_counts_by_level_link"
    )
    search_fields = ("code", "long_name")

    @admin.display(description="Curricula")
    def curri_count_link(self, obj: College):
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

    @admin.display(description="Crss")
    def crs_count_link(self, obj: College):
        count = obj.crs_count
        url = reverse("admin:academics_course_changelist") + (
            f"?department__college__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description="Departments")
    def dpt_chair_links(self, obj: College):
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
    def active_curra_list(self, obj: College):
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
    def inactive_curra_list(self, obj: College):
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

    fields = ("code", "long_name", "active_curra_list", "inactive_curra_list")
    readonly_fields = ("active_curra_list", "inactive_curra_list")

    @admin.display(description="Stds by level")
    def std_counts_by_level_link(self, obj: College):
        """Link to students filtered by college and computed level."""
        rows = []
        students = list(
            Student.objects.filter(
                curriculum_enrollments__curriculum__college=obj,
                curriculum_enrollments__is_primary=True,
            ).distinct()
        )
        for level in ("Freshman", "Sophomore", "Junior", "Senior"):
            count = sum(1 for s in students if getattr(s, "class_level", "") == level)
            url = reverse("admin:people_student_changelist") + (
                f"?curricula__college__id__exact={obj.id}&class_level={level}"
            )
            rows.append((url, level, count))
        return format_html_join(" | ", '<a href="{}">{}</a>: {}', rows)


@admin.register(CurriStatus)
class CurriStatusAdmin(admin.ModelAdmin):
    """Lookup admin for CurriStatus."""

    search_fields = ("code", "label")
    list_display = ("code", "label")


@admin.register(Department)
class DptAdmin(MergeWizardMixin, CollegeRestrictedAdmin):
    """Admin interface for :class:~app.academics.models.Department.

    Shows department code, name and college. autocomplete_fields speeds up
    college selection when editing a department.
    """

    resource_class = DptResource
    merge_fields = ("code", "long_name", "college")
    list_display = (
        "code",
        "long_name",
        "college",
        "crs_count_link",
        "faculty_count_link",
    )
    list_filter = [
        "college",
        DptCurriFltAC,
    ]
    list_editable = ("college",)
    search_fields = ("code", "long_name", "college__code", "college__long_name")
    inlines = [DptCrsIL]

    def get_queryset(self, request):
        # > explain the djangonic logic here
        qs = super().get_queryset(request)
        return qs.annotate(
            crs_count=Count("courses", distinct=True),
            faculty_total=Count(
                "courses__in_curriculum_courses__sections__faculty", distinct=True
            ),
        ).prefetch_related("courses__curricula")

    @admin.display(description="Crss", ordering="crs_count")
    def crs_count_link(self, obj):
        """Adding a link to the course number."""
        count = getattr(obj, "crs_count", None)
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
        summary = merge_dpts(target_department, source_departments)
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
    - list_filter uses :class:CurriFlt to narrow by curriculum.
    - actions provides update_curri for bulk updates.

    Example:
        On the prerequisites list page, select rows and run
        Attach / update curriculum to set a curriculum for them.
    """

    resource_class = PrerequisiteResource
    actions = [update_curri]

    # search_fields = ("course", "prerequisite_course") # not permitted no search of fk
    list_display = ("course", "prerequisite_course", "curriculum")
    autocomplete_fields = ("course", "prerequisite_course", "curriculum")
    list_filter = (CurriFltAC,)
    # search_fields = ("course", "prerequisite_course", "curriculum")


# NOTE:
# Advanced grouped prerequisite/corequisite admin stays intentionally unregistered.
# Keep this implementation nearby for later re-activation once the simple model
# transition is complete.

__all__ = ["CollegeAdmin", "CurriStatusAdmin", "DptAdmin", "PrerequisiteAdmin"]
