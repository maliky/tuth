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


def _quote_table(name: str) -> str:
    """Return a backend-quoted table identifier for generated admin SQL."""
    return connection.ops.quote_name(name)


def _crs_grade_total_expr() -> RawSQL:
    """Return a per-course grade count expression without a wide group-by."""
    from app.registry.models.grade import Grade
    from app.timetable.models.section import Section

    grade_table = _quote_table(Grade._meta.db_table)
    section_table = _quote_table(Section._meta.db_table)
    curri_crs_table = _quote_table(CurriCrs._meta.db_table)
    course_table = _quote_table(Course._meta.db_table)
    sql = (
        f"(SELECT COUNT({grade_table}.id) "
        f"FROM {grade_table} "
        f"INNER JOIN {section_table} "
        f"ON {grade_table}.section_id = {section_table}.id "
        f"INNER JOIN {curri_crs_table} "
        f"ON {section_table}.curriculum_course_id = {curri_crs_table}.id "
        f"WHERE {curri_crs_table}.course_id = {course_table}.id)"
    )
    return RawSQL(
        sql,
        params=(),
        output_field=IntegerField(),
    )


@admin.register(Course)
class CrsAdmin(DptRestrictedAdmin):
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

    resource_class = CrsResource
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
        CrsFeeStackIL,
        RequiresIL,
        PrerequisiteIL,
        CrsCurriIL,
    ]
    list_select_related = ("department",)
    list_editable = ("department",)
    list_filter = (
        SemFltAC,
        DptFltAC,
        CrsCurriFlt,
        CrsCollegeFlt,
    )

    list_per_page = 50
    list_max_show_all = 200

    search_fields = ("short_code", "department__code", "title")
    fields = ("code", "short_code", "department", "number", "title", "description")
    readonly_fields = ("code",)
    # Actions include manual merge and short_code-based merge helpers.
    actions = [
        update_dpt,
        attach_fee_stacks,
        merge_crss_action,
        merge_crss_by_short_code_action,
    ]

    def get_queryset(self, request):
        """Prefetch curricula for link rendering in list_display."""
        qs = super().get_queryset(request)
        qs = qs.prefetch_related("curricula").annotate(
            grade_total=_crs_grade_total_expr()
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
    def curra_links(self, obj: Course):
        """Link each curriculum name to its admin change page."""
        rows = [
            (
                reverse("admin:academics_curriculum_change", args=[cur.pk]),
                cur.short_name,
            )
            for cur in obj.curricula.all().order_by("short_name")
        ]
        if not rows:
            return "-"
        return format_html_join(", ", '<a href="{}">{}</a>', rows)

    @admin.display(description="Grades", ordering="grade_total")
    def grade_count(self, obj: Course) -> str:
        """Link to grades filtered to this course."""
        count = int(getattr(obj, "grade_total", 0) or 0)
        if not obj.pk:
            return str(count)
        url = (
            reverse("admin:registry_grade_changelist")
            + f"?section__curriculum_course__course__id__exact={obj.pk}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

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


__all__ = ["CrsAdmin"]
