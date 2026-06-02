"""ILs module."""

from django import forms
from django.contrib import admin
from collections import defaultdict
from typing import Any, Callable, cast

from django.forms.models import BaseInlineFormSet
from django.utils import timezone

from app.academics.models.prerequisite import Prerequisite
from app.academics.models.course import Course
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.requirement_group import (
    CurriCrsReqGp,
    CurriCrsReqMember,
)
from app.academics.models.concentration import (
    MajorCurriCrs,
    MinorCurriCrs,
)
from app.finance.models.fee_stack import CrsFeeStack
from app.timetable.models.semester import Semester


class RequiresIL(admin.TabularInline):
    """Inline editor for Prerequisite needed by a course."""

    model = Prerequisite
    fk_name = "course"
    verbose_name_plural = "Prerequisites this course needs"
    extra = 0
    autocomplete_fields = ("prerequisite_course",)
    ordering = ("prerequisite_course",)


class PrerequisiteIL(admin.TabularInline):
    """Inline showing courses that depend on the current course."""

    model = Prerequisite
    fk_name = "prerequisite_course"
    verbose_name_plural = "Crss that require this course"
    extra = 0
    autocomplete_fields = ("course",)
    ordering = ("course",)


class CrsCurriIL(admin.TabularInline):
    """Inline for linking  curriculum to course."""

    model = CurriCrs
    fk_name = "course"
    verbose_name_plural = "Curricula with this course."
    extra = 0
    autocomplete_fields = ("curriculum",)
    ordering = ("curriculum__college__code", "curriculum__short_name")
    template = "admin/academics/coursecurriculum/tabular_inline.html"
    fields = (
        "curriculum",
        "level_number",
        "required_group_number",
        "credit_hours",
        "min_validated_credits",
    )

    def get_queryset(self, request):
        """Select related labels used by the grouped inline template."""
        qs = super().get_queryset(request)
        return qs.select_related("course", "curriculum__college", "credit_hours")


class CrsFeeStackIL(admin.TabularInline):
    """Inline editor for linking fee stacks to courses."""

    model = CrsFeeStack
    fk_name = "course"
    verbose_name_plural = "Fee stacks"
    extra = 0
    autocomplete_fields = ("fee_stack",)
    fields = ("fee_stack", "current_stack_total")
    readonly_fields = ("current_stack_total",)
    ordering = ("fee_stack__name",)

    _semester_cache: Semester | None = None

    def _resolved_sem(self) -> Semester | None:
        """Return the latest started semester (or latest available)."""
        if self._semester_cache is not None:
            return self._semester_cache
        today = timezone.now().date()
        semester = (
            Semester.objects.filter(start_date__lte=today).order_by("-start_date").first()
        )
        if semester is None:
            semester = Semester.objects.order_by("-start_date").first()
        self._semester_cache = semester
        return semester

    @admin.display(description="Current stack total")
    def current_stack_total(self, obj: CrsFeeStack) -> str:
        """Show resolved stack total for the current semester context."""
        semester = self._resolved_sem()
        if obj is None or not obj.fee_stack_id:
            return "-"
        total = obj.fee_stack.total_amount_for_sem(semester)
        return f"{total:.2f}"


class CurriCrsSummaryFormSet(BaseInlineFormSet):
    """Inline formset that annotates group summary values."""

    summary_builder: Callable[[list[CurriCrs]], dict[tuple[int, int], dict[str, int]]]
    group_key_builder: Callable[[CurriCrs], tuple[int, int]]

    def get_queryset(self):
        """Attach summary attributes used by the inline template."""
        qs = (
            super()
            .get_queryset()
            .select_related("course", "curriculum__college", "credit_hours")
            .order_by(
                "year_number",
                "semester_number",
                "required_group_number",
                "course__code",
            )
        )
        summary_builder = getattr(self, "summary_builder", None)
        group_key_builder = getattr(self, "group_key_builder", None)
        if summary_builder is None or group_key_builder is None:
            return qs
        rows = list(qs)
        summary_map = summary_builder(rows)
        for row in rows:
            summary = summary_map.get(group_key_builder(row), {})
            row.group_course_count = summary.get("crs_count", 0)
            row.group_credit_total = summary.get("credit_total", 0)
        # > Keep enriched rows so template can read summary values.
        qs_cache = cast(Any, qs)
        qs_cache._result_cache = rows
        qs_cache._prefetch_done = True
        return qs


class CurriCrsIL(admin.TabularInline):
    """Inline for linking courses to a curriculum."""

    model = CurriCrs

    class CurriCrsInlineForm(forms.ModelForm):
        """Inline form with bulk relink toggle."""

        move_to_dpt_dft = forms.BooleanField(
            required=False,
            label="Move to dept default",
            help_text="Move this course to the department's default curriculum",
        )

        class Meta:
            model = CurriCrs
            fields = "__all__"

    form = CurriCrsInlineForm
    fk_name = "curriculum"
    verbose_name_plural = "Crss in this curriculum."
    extra = 0
    autocomplete_fields = ("course", "curriculum")
    ordering = (
        "year_number",
        "semester_number",
        "required_group_number",
        "course__code",
    )
    template = "admin/academics/curriculumcourse/tabular_inline.html"
    formset = CurriCrsSummaryFormSet
    fields = (
        "course",
        "level_number",
        "required_group_number",
        "credit_hours",
        "min_validated_credits",
        "move_to_dpt_dft",
    )
    readonly_fields = ()

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Rename required group field label for inline display."""
        form_field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "required_group_number" and form_field is not None:
            form_field.label = "Required group"
        return form_field

    def _gp_key(self, curriculum_course: CurriCrs) -> tuple[int, int]:
        """Return the (year, semester) key for summary grouping."""
        return (
            int(getattr(curriculum_course, "year_number", 0) or 0),
            int(getattr(curriculum_course, "semester_number", 0) or 0),
        )

    def _build_gp_summary(
        self, rows: list[CurriCrs]
    ) -> dict[tuple[int, int], dict[str, int]]:
        """Return summary stats keyed by year/semester."""
        summary_map: dict[tuple[int, int], dict[str, int]] = {}
        grouped: dict[tuple[int, int], list[CurriCrs]] = defaultdict(list)
        for row in rows:
            grouped[self._gp_key(row)].append(row)

        for group_key, group_rows in grouped.items():
            # Count each required group once; standalone courses are their own group.
            group_credit_map: dict[tuple[str, int], int] = {}
            for row in group_rows:
                credit_value = int(getattr(row, "credit_hours_id", 0) or 0)
                group_number = int(getattr(row, "required_group_number", 0) or 0)
                if group_number > 0:
                    key = ("group", group_number)
                else:
                    key = ("course", int(getattr(row, "pk", 0) or 0))
                if key in group_credit_map:
                    continue
                group_credit_map[key] = credit_value
            summary_map[group_key] = {
                "crs_count": len(group_credit_map),
                "credit_total": sum(group_credit_map.values()),
            }
        return summary_map

    def get_queryset(self, request):
        """Order curriculum-course rows for inline display."""
        qs = super().get_queryset(request)
        return qs.select_related(
            "course", "curriculum__college", "credit_hours"
        ).order_by(
            "year_number",
            "semester_number",
            "required_group_number",
            "course__code",
        )

    def get_formset(self, request, obj=None, **kwargs):
        """Attach group summaries to inline rows for template rendering."""
        formset = super().get_formset(request, obj, **kwargs)
        formset_class = cast(Any, formset)
        formset_class.summary_builder = self._build_gp_summary
        formset_class.group_key_builder = self._gp_key
        return formset

    # Student counts removed from inline to avoid slow/incorrect values.


class CurriCrsReqMemberIL(admin.TabularInline):
    """Inline editor for requirement group members."""

    # Dormant: this inline is intentionally not mounted in active admin screens.

    model = CurriCrsReqMember
    fk_name = "group"
    verbose_name = "Requirement member"
    verbose_name_plural = "Requirement members"
    extra = 0
    autocomplete_fields = ("required_course",)
    fields = ("required_course", "order")
    ordering = ("order", "required_course__short_code", "required_course__code")


class CurriCrsReqGpIL(admin.TabularInline):
    """Inline editor for requirement groups bound to a curriculum course."""

    # Dormant: keep implementation for later re-enable of advanced requirements UI.

    model = CurriCrsReqGp
    fk_name = "curriculum_course"
    verbose_name = "Requirement group"
    verbose_name_plural = "Requirement groups"
    extra = 0
    fields = ("kind", "label", "order", "member_count", "manage_members")
    readonly_fields = ("member_count", "manage_members")
    ordering = ("order", "id")

    @admin.display(description="Members")
    def member_count(self, obj: CurriCrsReqGp) -> int:
        """Return number of member courses in the group."""
        if not getattr(obj, "pk", None):
            return 0
        return obj.members.count()

    @admin.display(description="Manage members")
    def manage_members(self, obj: CurriCrsReqGp) -> str:
        """Link to group change page where member inline is available."""
        if not getattr(obj, "pk", None):
            return "Save first"
        # Requirement-group admin is intentionally not registered while the
        # advanced UI remains dormant.
        return "Not available"


class DptCrsIL(admin.TabularInline):
    """Inline courses of a department."""

    model = Course
    fk_name = "department"
    verbose_name_plural = "Crss offered by this department "
    extra = 0
    autocomplet_fields = ("course",)
    fields = ("short_code", "number", "title")
    ordering = ("short_code",)


class MajorCurriCrsIL(admin.TabularInline):
    """Inline editor for major membership rows."""

    model = MajorCurriCrs
    fk_name = "major"
    verbose_name_plural = "Major curriculum courses"
    extra = 0
    autocomplete_fields = ("curriculum_course",)
    ordering = (
        "curriculum_course__course__short_code",
        "curriculum_course__course__code",
    )


class MinorCurriCrsIL(admin.TabularInline):
    """Inline editor for minor membership rows."""

    model = MinorCurriCrs
    fk_name = "minor"
    verbose_name_plural = "Minor curriculum courses"
    extra = 0
    autocomplete_fields = ("curriculum_course",)
    ordering = (
        "curriculum_course__course__short_code",
        "curriculum_course__course__code",
    )
