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


@admin.register(CurriStdEnroll)
class CurriStdEnrollAdmin(CollegeRestrictedNoHistoryAdmin):
    """Admin interface for student program enrollments."""

    college_field = "curriculum__college"
    list_display = (
        "student",
        "curriculum",
        "is_primary",
        "is_active",
        "entry_semester",
    )
    list_filter = (
        "curriculum__college",
        CurriFltAC,
        "is_primary",
        "is_active",
    )
    search_fields = (
        "student__student_id",
        "student__long_name",
        "curriculum__short_name",
        "curriculum__long_name",
    )
    autocomplete_fields = ("student", "curriculum", "entry_semester", "exit_semester")
    list_select_related = ("student__user", "curriculum__college")
    actions = (
        "merge_two_selected_rows",
        "bulk_change_curri_on_selected_rows",
        "merge_selected_rows_by_std_id",
    )

    @staticmethod
    def _accumulate_std_record_summary(
        aggregate: StdCurriRecordMergeSummaryT,
        current: StdCurriRecordMergeSummaryT,
    ) -> None:
        """Merge current counters into aggregate in place."""
        for key, value in current.items():
            aggregate[key] += value

    @staticmethod
    def _reconciled_std_record_count(
        summary: StdCurriRecordMergeSummaryT,
    ) -> int:
        """Return the number of auto-reconciled student records."""
        return (
            summary["grades_moved"]
            + summary["grades_deduped"]
            + summary["registrations_moved"]
            + summary["registrations_deduped"]
        )

    @staticmethod
    def _unresolved_std_record_count(
        summary: StdCurriRecordMergeSummaryT,
    ) -> int:
        """Return the number of manual-review student records."""
        return (
            summary["grade_conflicts"]
            + summary["grades_unresolved"]
            + summary["registrations_unresolved"]
        )

    def _notify_std_record_summary(
        self,
        request,
        summary: StdCurriRecordMergeSummaryT,
    ) -> None:
        """Show one consistent reconciliation summary in admin messages."""
        if self._reconciled_std_record_count(summary):
            self.message_user(
                request,
                (
                    "Reconciled student records: "
                    f"{summary['grades_moved']} grade(s) moved, "
                    f"{summary['grades_deduped']} grade duplicate(s) removed, "
                    f"{summary['registrations_moved']} registration(s) moved, "
                    f"{summary['registrations_deduped']} registration duplicate(s) removed."
                ),
                level=messages.INFO,
            )
        if self._unresolved_std_record_count(summary):
            self.message_user(
                request,
                (
                    "Manual review required: "
                    f"{summary['grade_conflicts']} grade conflict(s), "
                    f"{summary['grades_unresolved']} grade(s) without target section match, "
                    f"{summary['registrations_unresolved']} registration(s) without target section match."
                ),
                level=messages.WARNING,
            )

    def _curri_action_queryset(self, request):
        """Return curriculum choices allowed for the current admin user."""
        queryset = Curriculum.objects.select_related("college").order_by(
            "short_name", "id"
        )
        if request.user.is_superuser:
            return queryset
        college = self.get_user_college(request)
        if college is None:
            return queryset
        return queryset.filter(college=college)

    @admin.action(description="Merge 2 selected enrollment rows")
    @transaction.atomic
    def merge_two_selected_rows(self, request, queryset):
        """Merge exactly two selected rows when semester rule allows it."""
        rows = list(queryset.select_related("student", "entry_semester").order_by("id"))
        if len(rows) != 2:
            self.message_user(
                request,
                "Select exactly 2 rows for this merge action.",
                level=messages.WARNING,
            )
            return
        target_row, source_row = rows[0], rows[1]
        if target_row.student_id != source_row.student_id:
            self.message_user(
                request,
                "Selected rows belong to different students; merge cancelled.",
                level=messages.WARNING,
            )
            return
        merged, student_record_summary = merge_std_enrollment_pair(
            target_row,
            source_row,
        )
        if not merged:
            self.message_user(
                request,
                "Merge blocked: both rows have different non-null entry semesters.",
                level=messages.WARNING,
            )
            return
        self.message_user(
            request,
            "Merged 2 enrollment rows into the lowest-id row.",
            level=messages.SUCCESS,
        )
        self._notify_std_record_summary(request, student_record_summary)

    @admin.action(description="Bulk change curriculum on selected rows")
    @transaction.atomic
    def bulk_change_curri_on_selected_rows(self, request, queryset):
        """Move selected enrollment rows to one target curriculum with safe merges."""

        class HiddenIdListField(forms.MultipleChoiceField):
            def validate(self, value):
                return

        class _CurriBulkChangeForm(forms.Form):
            _selected_action = HiddenIdListField(widget=forms.MultipleHiddenInput)
            curriculum = forms.ModelChoiceField(
                queryset=Curriculum.objects.none(),
                label="Target curriculum",
            )

            def __init__(self, *args, curriculum_queryset=None, **kwargs):
                super().__init__(*args, **kwargs)
                if curriculum_queryset is None:
                    curriculum_queryset = Curriculum.objects.none()
                curriculum_field = cast(forms.ModelChoiceField, self.fields["curriculum"])
                curriculum_field.queryset = curriculum_queryset

        selected_ids = request.POST.getlist(ACTION_CHECKBOX_NAME)
        selected_rows = list(
            queryset.filter(pk__in=selected_ids)
            .select_related("student", "curriculum", "entry_semester")
            .order_by("student_id", "id")
        )
        if not selected_rows and "apply_change_curri" not in request.POST:
            self.message_user(
                request,
                "Select at least one row for this action.",
                level=messages.WARNING,
            )
            return None

        if "apply_change_curri" in request.POST:
            form = _CurriBulkChangeForm(
                request.POST,
                curriculum_queryset=self._curri_action_queryset(request),
            )
            if form.is_valid():
                target_curri = form.cleaned_data["curriculum"]
                ordered_ids = [
                    int(raw_id)
                    for raw_id in form.cleaned_data["_selected_action"]
                    if str(raw_id).isdigit()
                ]
                moved_count = 0
                merged_count = 0
                already_in_target_count = 0
                blocked_count = 0
                missing_count = 0
                aggregate_student_summary = empty_std_curri_record_summary()

                for enroll_id in ordered_ids:
                    source_row = (
                        CurriStdEnroll.objects.select_related(
                            "student",
                            "curriculum",
                            "entry_semester",
                        )
                        .filter(pk=enroll_id)
                        .first()
                    )
                    if source_row is None:
                        missing_count += 1
                        continue
                    if source_row.curriculum_id == target_curri.id:
                        already_in_target_count += 1
                        continue

                    target_row = (
                        CurriStdEnroll.objects.select_related(
                            "student",
                            "curriculum",
                            "entry_semester",
                        )
                        .filter(
                            student_id=source_row.student_id,
                            curriculum=target_curri,
                        )
                        .exclude(pk=source_row.pk)
                        .order_by("id")
                        .first()
                    )
                    if target_row is None:
                        source_row.curriculum = target_curri
                        source_row.save(update_fields=["curriculum"])
                        moved_count += 1
                        continue

                    # Reuse the same guard + reconciliation path as pair merge.
                    merged, student_record_summary = merge_std_enrollment_pair(
                        target_row,
                        source_row,
                    )
                    self._accumulate_std_record_summary(
                        aggregate_student_summary,
                        student_record_summary,
                    )
                    if merged:
                        merged_count += 1
                        continue
                    blocked_count += 1

                if moved_count:
                    self.message_user(
                        request,
                        f"Moved {moved_count} enrollment row(s) to {target_curri}.",
                        level=messages.SUCCESS,
                    )
                if merged_count:
                    self.message_user(
                        request,
                        (
                            "Merged "
                            f"{merged_count} row(s) into existing {target_curri} "
                            "enrollment rows."
                        ),
                        level=messages.SUCCESS,
                    )
                if already_in_target_count:
                    self.message_user(
                        request,
                        (
                            "Skipped "
                            f"{already_in_target_count} row(s) already linked to "
                            f"{target_curri}."
                        ),
                        level=messages.INFO,
                    )
                if blocked_count:
                    self.message_user(
                        request,
                        (
                            "Skipped "
                            f"{blocked_count} row(s) because entry semesters were "
                            "both set and different."
                        ),
                        level=messages.WARNING,
                    )
                if missing_count:
                    self.message_user(
                        request,
                        f"Skipped {missing_count} missing row(s).",
                        level=messages.INFO,
                    )

                self._notify_std_record_summary(request, aggregate_student_summary)
                if (
                    moved_count == 0
                    and merged_count == 0
                    and already_in_target_count == 0
                    and blocked_count == 0
                    and missing_count == 0
                ):
                    self.message_user(
                        request,
                        "No row changed for this action.",
                        level=messages.INFO,
                    )
                return None
        else:
            form = _CurriBulkChangeForm(
                initial={
                    "_selected_action": [str(row.pk) for row in selected_rows],
                },
                curriculum_queryset=self._curri_action_queryset(request),
            )

        context = {
            **self.admin_site.each_context(request),
            "title": "Bulk change curriculum on selected enrollment rows",
            "form": form,
            "rows": selected_rows,
            "opts": self.model._meta,
            "action_name": "bulk_change_curri_on_selected_rows",
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
        }
        return TemplateResponse(
            request,
            "admin/academics/curristdenroll/bulk_change_curriculum.html",
            context,
        )

    @admin.action(description="Merge selected rows grouped by student id")
    @transaction.atomic
    def merge_selected_rows_by_std_id(self, request, queryset):
        """Merge selected rows per student id using the same semester guard."""
        rows = list(
            queryset.select_related("student", "entry_semester")
            .order_by("student_id", "id")
            .all()
        )
        if len(rows) < 2:
            self.message_user(
                request,
                "Select at least 2 rows to run grouped merge.",
                level=messages.WARNING,
            )
            return

        merged_count = 0
        blocked_count = 0
        grouped_count = 0
        aggregate_student_summary = empty_std_curri_record_summary()
        by_student_id: dict[int, list[StdCurriEnroll]] = {}
        for row in rows:
            by_student_id.setdefault(row.student_id, []).append(row)

        for student_rows in by_student_id.values():
            if len(student_rows) < 2:
                continue
            grouped_count += 1
            target_row = student_rows[0]
            for source_row in student_rows[1:]:
                merged, student_record_summary = merge_std_enrollment_pair(
                    target_row,
                    source_row,
                )
                self._accumulate_std_record_summary(
                    aggregate_student_summary,
                    student_record_summary,
                )
                if merged:
                    merged_count += 1
                    continue
                blocked_count += 1

        if merged_count:
            self.message_user(
                request,
                (
                    f"Merged {merged_count} row(s) across {grouped_count} student group(s)."
                ),
                level=messages.SUCCESS,
            )
        if blocked_count:
            self.message_user(
                request,
                (
                    "Skipped "
                    f"{blocked_count} row(s) because entry semesters were both set and "
                    "different."
                ),
                level=messages.WARNING,
            )
        self._notify_std_record_summary(request, aggregate_student_summary)
        if not merged_count and not blocked_count:
            self.message_user(
                request,
                "No student groups with at least 2 selected rows were found.",
                level=messages.INFO,
            )


__all__ = ["CurriStdEnrollAdmin"]
