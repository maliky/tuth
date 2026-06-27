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
    CurriCollegeFltAC,
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


class CurriMergeConflictForm(forms.Form):
    """Collect target selection, curriculum field picks, and conflict decisions."""

    FIELD_FROM_TARGET: MergeFieldSourceChoiceT = "target"
    FIELD_FROM_SOURCE: MergeFieldSourceChoiceT = "source"
    CONFLICT_FIELD_PREFIX = "conflict__"
    MERGE_FIELD_PREFIX = "field__"

    def __init__(
        self,
        *,
        curricula: list[Curriculum],
        merge_fields: tuple[str, ...],
        conflict_course_ids: list[int],
        data=None,
    ) -> None:
        super().__init__(data=data)
        self._curriculum_map = {
            str(item.pk): item for item in curricula if item.pk is not None
        }
        self._merge_fields = merge_fields
        self._conflict_course_ids = conflict_course_ids
        target_choices = [
            (str(item.pk), self._curri_label(item))
            for item in curricula
            if item.pk is not None
        ]
        self.fields["target_id"] = forms.ChoiceField(
            label="Target curriculum",
            choices=target_choices,
            required=True,
        )
        self.fields["target_id"].initial = (
            target_choices[0][0] if target_choices else None
        )
        for field_name in merge_fields:
            self.fields[self.merge_field_key(field_name)] = forms.ChoiceField(
                label=self._field_label(field_name),
                choices=(
                    (self.FIELD_FROM_TARGET, "Keep target value"),
                    (self.FIELD_FROM_SOURCE, "Use source value"),
                ),
                widget=forms.RadioSelect,
                required=True,
                initial=self.FIELD_FROM_TARGET,
            )
        for course_id in conflict_course_ids:
            self.fields[self.conflict_field_key(course_id)] = forms.ChoiceField(
                label=f"Conflict action for course #{course_id}",
                choices=(
                    (MERGE_CHOICE_KEEP_TARGET, "Keep target row"),
                    (MERGE_CHOICE_KEEP_SOURCE, "Keep source values"),
                    (MERGE_CHOICE_MERGE, "Merge sections/grades"),
                    (MERGE_CHOICE_SKIP, "Skip this course"),
                ),
                required=True,
                initial=MERGE_CHOICE_MERGE,
            )

    @staticmethod
    def _curri_label(item: Curriculum) -> str:
        """Build a compact curriculum label for merge choices."""
        college_code = getattr(getattr(item, "college", None), "code", "-")
        return f"{item.short_name} ({college_code})"

    @classmethod
    def merge_field_key(cls, field_name: str) -> str:
        """Return the POST key used by one curriculum field merge choice."""
        return f"{cls.MERGE_FIELD_PREFIX}{field_name}"

    @classmethod
    def conflict_field_key(cls, course_id: int) -> str:
        """Return the POST key used by one conflicting course choice."""
        return f"{cls.CONFLICT_FIELD_PREFIX}{course_id}"

    @staticmethod
    def _field_label(field_name: str) -> str:
        """Convert a model field name to a readable admin label."""
        return field_name.replace("_", " ").title()

    def clean_target_id(self) -> str:
        """Validate target_id against selected curricula."""
        target_id = str(self.cleaned_data["target_id"])
        if target_id not in self._curriculum_map:
            raise forms.ValidationError("Selected target is not in the action selection.")
        return target_id

    def field_value_source(self, field_name: str) -> MergeFieldSourceChoiceT:
        """Return whether a field should come from target or source curriculum."""
        key = self.merge_field_key(field_name)
        selected = self.cleaned_data.get(key, self.FIELD_FROM_TARGET)
        if selected == self.FIELD_FROM_SOURCE:
            return self.FIELD_FROM_SOURCE
        return self.FIELD_FROM_TARGET

    def get_conflict_choices(self) -> ConflictChoiceByCrsIdT:
        """Return validated conflict choices keyed by course id."""
        choices: ConflictChoiceByCrsIdT = {}
        for course_id in self._conflict_course_ids:
            field_name = self.conflict_field_key(course_id)
            raw_choice = self.cleaned_data.get(field_name, MERGE_CHOICE_MERGE)
            if raw_choice not in {
                MERGE_CHOICE_KEEP_TARGET,
                MERGE_CHOICE_KEEP_SOURCE,
                MERGE_CHOICE_MERGE,
                MERGE_CHOICE_SKIP,
            }:
                continue
            choices[course_id] = raw_choice
        return choices


@admin.register(Curriculum)
class CurriAdmin(MergeWizardMixin, CollegeRestrictedAdmin):
    """Admin options for Curriculum.

    Key features:
    - inlines manage related curriculum courses inline.
    - list_display includes short and long names with the college.
    - list_filter allows filtering by college and active state.
    """

    resource_class = CurriResource
    # add the action button on the import form
    list_display = (
        "short_name",
        "long_name",
        "college",
        "is_active",
        "status",
        "crs_count_link",
        "std_count",
    )
    list_filter = (SemFltAC, CurriCollegeFltAC, "is_active", "status")
    list_editable = ("status", "is_active")
    autocomplete_fields = ("college",)
    inlines = [CurriCrsIL]

    # list_selected_relate reduces the number of queries in db
    list_select_related = ("college",)
    search_fields = ("short_name", "long_name")
    # Keep short_name out of the wizard to avoid active-name uniqueness collisions.
    merge_fields = ("long_name", "college", "status", "is_active", "description")
    actions = ["export_prereq_graph_action", "copy_curri_action"]

    def std_count(self, obj):
        """Adding a link to the student number."""
        count = obj.current_std_count()
        url = reverse("admin:people_student_changelist") + (
            f"?curriculum__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    def save_formset(self, request, form, formset, change):
        """Handle inline moves to department default curricula."""
        super().save_formset(request, form, formset, change)
        if formset.model is not CurriCrs:
            return

        selected_ids: list[int] = []
        for inline_form in formset.forms:
            cleaned = getattr(inline_form, "cleaned_data", None)
            if not cleaned:
                continue
            if cleaned.get("DELETE"):
                continue
            if not cleaned.get("move_to_dpt_dft"):
                continue
            instance = inline_form.instance
            if instance.pk:
                selected_ids.append(instance.pk)

        if not selected_ids:
            return

        selected_rows = list(
            CurriCrs.objects.filter(pk__in=selected_ids)
            .select_related("course__department__college")
            .order_by("id")
        )
        if not selected_rows:
            return

        dft_curri_by_college_id: dict[int, Curriculum] = {}

        def _resolve_target(curriculum_course: CurriCrs) -> Curriculum | None:
            dept = getattr(curriculum_course.course, "department", None)
            if dept is None or dept.college_id is None:
                return None
            target_curri = dft_curri_by_college_id.get(dept.college_id)
            if target_curri is not None:
                return target_curri
            target_curri = Curriculum.get_dft(def_college=dept.college)
            dft_curri_by_college_id[dept.college_id] = target_curri
            return target_curri

        with transaction.atomic():
            summary = _apply_curri_relink(
                selected_rows=selected_rows,
                resolve_target_curri=_resolve_target,
            )
        _notify_curri_relink_result(
            modeladmin=self,
            request=request,
            summary=summary,
        )
        if dft_curri_by_college_id:
            self.message_user(
                request,
                (
                    "Resolved "
                    f"{len(dft_curri_by_college_id)} default curriculum target(s) "
                    "from selected departments."
                ),
                messages.INFO,
            )

    @admin.display(description="Crss")
    def crs_count_link(self, obj):
        """Link course counts to the course changelist for this curriculum."""
        count = obj.crs_count()
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

    def _build_copy_short_name(self, source: Curriculum) -> str:
        """Return a readable short name for a copied curriculum."""
        max_len = int(Curriculum._meta.get_field("short_name").max_length or 40)
        base_seed = source.short_name.strip() or "Curriculum"
        base = f"{base_seed} copy".strip()[:max_len]
        candidate = base
        idx = 2
        while Curriculum.objects.filter(
            college=source.college, short_name=candidate
        ).exists():
            suffix = f" {idx}"
            keep_len = max(1, max_len - len(suffix))
            candidate = f"{base[:keep_len]}{suffix}"
            idx += 1
        return candidate

    @admin.action(description="Copy curriculum with courses")
    def copy_curri_action(self, request, queryset):
        """Duplicate selected curricula and clone their programmed courses."""
        if not queryset:
            self.message_user(request, "No curricula selected.", level=messages.WARNING)
            return

        created_rows: list[tuple[str, str, int]] = []
        selected = queryset.select_related("college")
        for source in selected:
            try:
                with transaction.atomic():
                    target = Curriculum.objects.create(
                        short_name=self._build_copy_short_name(source),
                        long_name=source.long_name,
                        college=source.college,
                        description=source.description,
                        status_id="pending",
                        is_active=False,
                    )
                    source_rows = CurriCrs.objects.filter(curriculum=source)
                    for row in source_rows:
                        CurriCrs.objects.create(
                            curriculum=target,
                            course_id=row.course_id,
                            is_required=row.is_required,
                            is_elective=row.is_elective,
                            credit_hours_id=row.credit_hours_id,
                            semester_number=row.semester_number,
                            level_number=row.level_number,
                            year_number=row.year_number,
                            required_group_number=row.required_group_number,
                            min_validated_credits=row.min_validated_credits,
                        )
                    copy_count = source_rows.count()
                copy_url = reverse("admin:academics_curriculum_change", args=[target.pk])
                created_rows.append((copy_url, target.short_name, copy_count))
            except Exception as exc:  # pragma: no cover - admin message path
                self.message_user(
                    request,
                    f"Failed to copy {source.short_name}: {exc}",
                    level=messages.ERROR,
                )

        if not created_rows:
            return
        links = format_html_join(
            " · ",
            '<a href="{}">{}</a> ({} courses)',
            created_rows,
        )
        self.message_user(
            request,
            format_html("Created curriculum copies: {}.", links),
            level=messages.SUCCESS,
        )

    def merge_records_action(self, request, queryset):
        """Merge exactly two curricula with per-conflict decisions."""
        selected_ids = request.POST.getlist(ACTION_CHECKBOX_NAME)
        candidates = list(
            queryset.filter(pk__in=selected_ids).select_related("college").order_by("id")
        )
        if len(candidates) != 2:
            self.message_user(
                request,
                "Select exactly two curricula to run the guided merge.",
                level=messages.WARNING,
            )
            return None

        target_id_hint = request.POST.get("target_id")
        target = candidates[0]
        if target_id_hint:
            hinted = next(
                (item for item in candidates if str(item.pk) == str(target_id_hint)),
                None,
            )
            if hinted is not None:
                target = hinted
        source = next(item for item in candidates if item.pk != target.pk)
        conflicts, non_conflicting = list_curri_crs_conflicts(target, source)
        conflict_course_ids = [
            source_row.course_id for _target_row, source_row in conflicts
        ]
        form_data = request.POST if request.POST.get("apply_merge") else None
        form = CurriMergeConflictForm(
            data=form_data,
            curricula=candidates,
            merge_fields=self.get_merge_fields(request),
            conflict_course_ids=conflict_course_ids,
        )
        if request.POST.get("apply_merge") and form.is_valid():
            target_id = form.cleaned_data["target_id"]
            target = next(item for item in candidates if str(item.pk) == str(target_id))
            source = next(item for item in candidates if item.pk != target.pk)
            # Recompute conflicts for the selected target/source orientation.
            conflicts, _ = list_curri_crs_conflicts(target, source)
            updated_fields: list[str] = []
            merge_fields = self.get_merge_fields(request)
            for field_name in merge_fields:
                if form.field_value_source(field_name) != form.FIELD_FROM_SOURCE:
                    continue
                source_value = getattr(source, field_name)
                if getattr(target, field_name) == source_value:
                    continue
                setattr(target, field_name, source_value)
                updated_fields.append(field_name)
            conflict_choices = form.get_conflict_choices()
            # Keep a stable transaction for both target updates and merge moves.
            with transaction.atomic():
                if updated_fields:
                    target.save(update_fields=updated_fields)
                summary = merge_curra(
                    target,
                    [source],
                    conflict_choices=conflict_choices,
                )
            self._msg_curri_merge_summary(request, target, summary)
            return None

        merge_field_rows = [
            {
                "label": field_name.replace("_", " ").title(),
                "field": form[CurriMergeConflictForm.merge_field_key(field_name)],
            }
            for field_name in self.get_merge_fields(request)
        ]
        conflict_rows = []
        for target_row, source_row in conflicts:
            field_key = CurriMergeConflictForm.conflict_field_key(source_row.course_id)
            conflict_rows.append(
                {
                    "target_row": target_row,
                    "source_row": source_row,
                    "target_sections": target_row.sections.count(),
                    "source_sections": source_row.sections.count(),
                    "source_invoices": Invoice.objects.filter(
                        curriculum_course=source_row
                    ).count(),
                    "field": form[field_key],
                }
            )

        context = {
            "title": "Guided curriculum merge",
            "form": form,
            "objects": candidates,
            "action_name": "merge_records_action",
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
            "target": target,
            "source": source,
            "merge_field_rows": merge_field_rows,
            "conflict_rows": conflict_rows,
            "non_conflicting": non_conflicting,
            "merge_choice_merge": MERGE_CHOICE_MERGE,
            "merge_choice_keep_target": MERGE_CHOICE_KEEP_TARGET,
            "merge_choice_keep_source": MERGE_CHOICE_KEEP_SOURCE,
            "merge_choice_skip": MERGE_CHOICE_SKIP,
        }
        return TemplateResponse(
            request,
            "admin/academics/curriculum/merge_curricula_conflicts.html",
            context,
        )

    merge_records_action.short_description = "Guided merge selected curricula"  # type: ignore[attr-defined]

    def _msg_curri_merge_summary(
        self,
        request,
        target: Curriculum,
        summary: dict[str, int],
    ) -> None:
        """Emit consistent merge feedback messages for curriculum merges."""
        self.message_user(
            request,
            (
                f"Merged {summary['curricula_merged']} curriculum/curricula into "
                f"{target.short_name}."
            ),
            level=messages.SUCCESS,
        )
        if summary["curricula_retained"]:
            self.message_user(
                request,
                (
                    "Some source curricula were retained due to conflicts. "
                    "Review the per-course choices and invoice blockers."
                ),
                level=messages.WARNING,
            )
        if summary["conflicts_merged"]:
            self.message_user(
                request,
                f"Merged {summary['conflicts_merged']} conflicting course row(s).",
                level=messages.INFO,
            )
        if summary["conflicts_kept_target"]:
            self.message_user(
                request,
                (
                    "Kept the target programmed course for "
                    f"{summary['conflicts_kept_target']} conflict(s)."
                ),
                level=messages.INFO,
            )
        if summary["conflicts_kept_source"]:
            self.message_user(
                request,
                (
                    "Applied source programmed-course values for "
                    f"{summary['conflicts_kept_source']} conflict(s)."
                ),
                level=messages.INFO,
            )
        if summary["conflicts_skipped"]:
            self.message_user(
                request,
                f"Skipped {summary['conflicts_skipped']} conflict(s) by choice.",
                level=messages.WARNING,
            )
        if summary["sections_merged"]:
            self.message_user(
                request,
                f"Merged {summary['sections_merged']} conflicting section(s).",
                level=messages.WARNING,
            )
        if summary["sections_skipped_grade_conflict"]:
            self.message_user(
                request,
                (
                    "Skipped "
                    f"{summary['sections_skipped_grade_conflict']} section merge(s) "
                    "because overlapping students had different grade values."
                ),
                level=messages.WARNING,
            )
        if summary.get("sections_rebucketed_sem0", 0):
            self.message_user(
                request,
                (
                    "Rebucketed "
                    f"{summary['sections_rebucketed_sem0']} sem0 section conflict(s) "
                    "into semesters 1..3."
                ),
                level=messages.INFO,
            )
        if summary.get("sections_blocked_sem0_overflow", 0):
            self.message_user(
                request,
                (
                    "Blocked "
                    f"{summary['sections_blocked_sem0_overflow']} sem0 conflict(s) "
                    "because no free semester slot (1..3) was available."
                ),
                level=messages.WARNING,
            )
        if summary["prerequisites_skipped"]:
            self.message_user(
                request,
                f"Skipped {summary['prerequisites_skipped']} duplicate prerequisite(s).",
                level=messages.WARNING,
            )
        if summary["skipped_invoices"]:
            self.message_user(
                request,
                f"Skipped {summary['skipped_invoices']} curriculum course(s) with invoices.",
                level=messages.WARNING,
            )
        if summary["credit_hours_conflicts"]:
            self.message_user(
                request,
                (
                    "Credit hours differ on "
                    f"{summary['credit_hours_conflicts']} curriculum course(s)."
                ),
                level=messages.WARNING,
            )
        if summary["is_required_conflicts"]:
            self.message_user(
                request,
                (
                    "Required flag differs on "
                    f"{summary['is_required_conflicts']} curriculum course(s)."
                ),
                level=messages.WARNING,
            )
        if summary["is_elective_conflicts"]:
            self.message_user(
                request,
                (
                    "Elective flag differs on "
                    f"{summary['is_elective_conflicts']} curriculum course(s)."
                ),
                level=messages.WARNING,
            )
        if summary["sections_retained_protected"]:
            self.message_user(
                request,
                (
                    "Retained "
                    f"{summary['sections_retained_protected']} conflicting section(s) "
                    "because grades still protect them."
                ),
                level=messages.WARNING,
            )
        if summary["protected_deletes"]:
            self.message_user(
                request,
                (
                    "Could not delete "
                    f"{summary['protected_deletes']} source object(s) because grades "
                    "protect related sections."
                ),
                level=messages.WARNING,
            )

    def merge_records(self, target: ModelT, sources: Iterable[ModelT]) -> dict[str, int]:
        """Merge curricula using the shared merge helper."""
        target_curriculum = cast(Curriculum, target)
        source_curricula = cast(Iterable[Curriculum], sources)
        request = getattr(self, "_merge_request", None)
        self._warn_curri_merge_precheck(
            request,
            target_curriculum,
            source_curricula,
        )
        summary = merge_curra(target_curriculum, source_curricula)
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
            "sections_skipped_grade_conflict": summary.get(
                "sections_skipped_grade_conflict", 0
            ),
            "sections_rebucketed_sem0": summary.get("sections_rebucketed_sem0", 0),
            "sections_blocked_sem0_overflow": summary.get(
                "sections_blocked_sem0_overflow", 0
            ),
            "skipped_invoices": summary.get("skipped_invoices", 0),
            "credit_hours_conflicts": summary.get("credit_hours_conflicts", 0),
            "is_required_conflicts": summary.get("is_required_conflicts", 0),
            "is_elective_conflicts": summary.get("is_elective_conflicts", 0),
        }

    # Avoid mypy internal error on the nested curriculum overlap query.
    @no_type_check
    def _warn_curri_merge_precheck(
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
        overlap_count = CurriCrs.objects.filter(
            curriculum=target,
            course_id__in=CurriCrs.objects.filter(curriculum_id__in=source_ids).values(
                "course_id"
            ),
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


__all__ = ["CurriAdmin", "CurriMergeConflictForm"]
