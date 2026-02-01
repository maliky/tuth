"""Inlines module."""

from django.contrib import admin
from collections import defaultdict
from typing import Any, Callable, cast

from django.db.models import Count
from django.forms.models import BaseInlineFormSet
from django.urls import reverse
from django.utils.html import format_html

from app.academics.models.prerequisite import Prerequisite
from app.academics.models.course import Course
from app.academics.models.curriculum_course import CurriculumCourse
from app.finance.models.course_fee import CourseFee, CurriculumCourseFee


class RequiresInline(admin.TabularInline):
    """Inline editor for Prerequisite needed by a course."""

    model = Prerequisite
    fk_name = "course"
    verbose_name_plural = "Prerequisites this course needs"
    extra = 0
    autocomplete_fields = ("prerequisite_course",)
    ordering = ("prerequisite_course",)


class PrerequisiteInline(admin.TabularInline):
    """Inline showing courses that depend on the current course."""

    model = Prerequisite
    fk_name = "prerequisite_course"
    verbose_name_plural = "Courses that require this course"
    extra = 0
    autocomplete_fields = ("course",)
    ordering = ("course",)


class CourseCurriculumInline(admin.TabularInline):
    """Inline for linking  curriculum to course."""

    model = CurriculumCourse
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
    )


class CourseFeeInline(admin.TabularInline):
    """Inline editor for course fees."""

    model = CourseFee
    fk_name = "course"
    verbose_name_plural = "Course fees"
    extra = 0
    autocomplete_fields = ("semester", "fee_type")
    fields = ("fee_type", "amount", "semester")
    ordering = ("semester",)


class CurriculumCourseFeeInline(admin.TabularInline):
    """Inline editor for curriculum course fees."""

    model = CurriculumCourseFee
    fk_name = "curriculum_course"
    verbose_name_plural = "Curriculum course fees"
    extra = 0
    autocomplete_fields = ("semester", "fee_type")
    fields = ("fee_type", "amount", "semester")
    ordering = ("semester",)


class CurriculumCourseSummaryFormSet(BaseInlineFormSet):
    """Inline formset that annotates group summary values."""

    summary_builder: Callable[
        [list[CurriculumCourse]], dict[tuple[int, int], dict[str, int]]
    ]
    group_key_builder: Callable[[CurriculumCourse], tuple[int, int]]

    def get_queryset(self):
        """Attach summary attributes used by the inline template."""
        qs = (
            super()
            .get_queryset()
            .annotate(
                student_total=Count(
                    "sections__section_registrations__student",
                    distinct=True,
                )
            )
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
            row.group_course_count = summary.get("course_count", 0)
            row.group_credit_total = summary.get("credit_total", 0)
        # > Keep enriched rows so template can read summary values.
        qs_cache = cast(Any, qs)
        qs_cache._result_cache = rows
        qs_cache._prefetch_done = True
        return qs


class CurriculumCourseInline(admin.TabularInline):
    """Inline for linking courses to a curriculum."""

    model = CurriculumCourse
    fk_name = "curriculum"
    verbose_name_plural = "Courses in this curriculum."
    extra = 0
    autocomplete_fields = ("course", "curriculum")
    ordering = (
        "year_number",
        "semester_number",
        "required_group_number",
        "course__code",
    )
    template = "admin/academics/curriculumcourse/tabular_inline.html"
    formset = CurriculumCourseSummaryFormSet
    fields = (
        "level_number",
        "course",
        "required_group_number",
        "credit_hours",
    )
    readonly_fields = ()

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Rename required group field label for inline display."""
        form_field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "required_group_number" and form_field is not None:
            form_field.label = "Required group"
        return form_field

    def _group_key(self, curriculum_course: CurriculumCourse) -> tuple[int, int]:
        """Return the (year, semester) key for summary grouping."""
        return (
            int(getattr(curriculum_course, "year_number", 0) or 0),
            int(getattr(curriculum_course, "semester_number", 0) or 0),
        )

    def _build_group_summary(
        self, rows: list[CurriculumCourse]
    ) -> dict[tuple[int, int], dict[str, int]]:
        """Return summary stats keyed by year/semester."""
        summary_map: dict[tuple[int, int], dict[str, int]] = {}
        grouped: dict[tuple[int, int], list[CurriculumCourse]] = defaultdict(list)
        for row in rows:
            grouped[self._group_key(row)].append(row)

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
                "course_count": len(group_credit_map),
                "credit_total": sum(group_credit_map.values()),
            }
        return summary_map

    def get_queryset(self, request):
        """Order curriculum-course rows for inline display."""
        qs = super().get_queryset(request)
        return qs.order_by(
            "year_number",
            "semester_number",
            "required_group_number",
            "course__code",
        )

    def get_formset(self, request, obj=None, **kwargs):
        """Attach group summaries to inline rows for template rendering."""
        formset = super().get_formset(request, obj, **kwargs)
        formset_class = cast(Any, formset)
        formset_class.summary_builder = self._build_group_summary
        formset_class.group_key_builder = self._group_key
        return formset

    # Student counts removed from inline to avoid slow/incorrect values.


class DepartmentCourseInline(admin.TabularInline):
    """Inline courses of a department."""

    model = Course
    fk_name = "department"
    verbose_name_plural = "Courses offered by this department "
    extra = 0
    autocomplet_fields = ("course",)
    fields = ("short_code", "number", "title")
    ordering = ("short_code",)
