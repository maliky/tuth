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


@admin.register(CurriCrs)
class CurriCrsAdmin(ProtectedDeleteAdminMixin, MergeWizardMixin, CollegeRestrictedAdmin):
    """Admin screen for :class:~app.academics.models.CurriCrs.

    list_display shows the curriculum and related course while
    autocomplete_fields make lookups faster. list_select_related joins
    both relations for efficient queries.
    """

    resource_class = CurriCrsResource
    college_field = "curriculum__college"
    merge_fields = (
        "curriculum",
        "course",
        "credit_hours",
        "is_required",
        "is_elective",
    )
    list_display = (
        "crs_display",
        "dpt_link",
        "curriculum",
        "level_number",
        # Keep list compact; min_validated_credits remains editable on the form view.
        "sec_count_link",
        "faculties_links",
    )
    list_filter = (
        SemFltAC,
        "curriculum__college",
        CurriFltAC,
        DptFltAC,
        "level_number",
        CurriCrsFacultyFltAC,
        CurriCrsStdFltAC,
    )

    list_editable = ("curriculum", "level_number")
    autocomplete_fields = ("curriculum", "course")
    list_select_related = ("curriculum", "course")
    # Include short_code to support curriculum course autocomplete lookups.
    search_fields = ("curriculum__short_name", "course__code", "course__short_code")
    list_per_page = 100
    list_max_show_all = 500

    # Optional inline to list all curricula for this curriculum_course.
    # Advanced requirement-group UI is intentionally hidden for now.
    inlines = ()

    ordering = ("course__short_code",)
    actions = [update_curri, update_curri_to_dpt_college_dft, update_level_number]

    def get_queryset(self, request):
        """Annotate section totals and prefetch faculty for list_display."""
        qs = super().get_queryset(request)
        return (
            qs.select_related("course__department")
            .prefetch_related("sections__faculty__staff_profile__user")
            .annotate(section_total=Count("sections", distinct=True))
        )

    def get_protected_delete_single_msg(self, request, obj, protected_count: int) -> str:
        """Return curriculum-course specific message for protected single deletes."""
        return (
            "Cannot delete programmed course because grades depend on one or more "
            f"related sections ({protected_count} protected record(s)). Reassign "
            "grades first."
        )

    def get_protected_delete_bulk_msg(self, request, protected_count: int) -> str:
        """Return curriculum-course specific message for protected bulk deletes."""
        return (
            "Bulk delete stopped: some programmed courses still have grade-protected "
            f"sections ({protected_count} protected record(s)). Reassign grades first."
        )

    def merge_object_label(self, obj) -> str:
        """Return a label for merge choices."""
        curriculum_course = cast(CurriCrs, obj)
        course = curriculum_course.course
        curriculum = curriculum_course.curriculum
        course_label = course.short_code or course.code or str(course)
        curriculum_label = curriculum.short_name or curriculum.long_name
        return f"{curriculum_label} | {course_label}"

    def merge_records(self, target, sources):
        """Merge curriculum courses into the target selection."""
        target_course = cast(CurriCrs, target)
        return merge_curri_crss(target_course, sources)

    @admin.display(description="Course")
    def crs_display(self, obj: CurriCrs) -> str:
        """Truncate course display to avoid very long values in list view."""
        return Truncator(str(obj.course)).chars(50)

    @admin.display(description="Department")
    def dpt_link(self, obj: CurriCrs):
        """Link to departments filtered to this course's department."""
        dept = getattr(obj.course, "department", None)
        if not dept:
            return "-"
        url = reverse("admin:academics_course_changelist") + (f"?department={dept.id}")
        return format_html('<a href="{}">{}</a>', url, dept.shortname)

    @admin.display(description="Sections", ordering="section_total")
    def sec_count_link(self, obj):
        """Link to sections filtered by this curriculum course."""
        count = getattr(obj, "section_total", None)
        if count is None:
            count = obj.sections.count()
        url = reverse("admin:timetable_section_changelist") + (
            f"?curriculum_course__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    # Advanced requirement-group link is kept dormant until the model is re-enabled.
    @admin.display(description="Requirement groups")
    def req_gps_link(self, obj: CurriCrs):
        """Return requirement-group count when dormant advanced UI is re-enabled."""
        return obj.requirement_groups.count()

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


__all__ = ["CurriCrsAdmin"]
