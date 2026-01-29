"""Inlines module."""

from django.contrib import admin
from collections import defaultdict
from typing import Any, cast

from django.db.models import Count
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
    ordering = ("course",)


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


class CurriculumCourseInline(admin.TabularInline):
    """Inline for linking courses to a curriculum."""

    model = CurriculumCourse
    fk_name = "curriculum"
    verbose_name_plural = "Courses in this curriculum."
    extra = 0
    autocomplete_fields = ("course", "curriculum")
    ordering = ("year_number", "semester_number", "course__code")
    template = "admin/academics/curriculumcourse/tabular_inline.html"
    fields = (
        "year_number",
        "semester_number",
        "course",
        "required_group_number",
        "credit_hours",
        "student_count_link",
    )
    readonly_fields = ("student_count_link",)

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
        """Annotate student totals for curriculum-course rows."""
        qs = super().get_queryset(request)
        qs = qs.annotate(
            student_total=Count("sections__section_registrations__student", distinct=True)
        ).order_by("year_number", "semester_number", "course__code")
        rows = list(qs)
        summary_map = self._build_group_summary(rows)
        for row in rows:
            summary = summary_map.get(self._group_key(row), {})
            row.group_course_count = summary.get("course_count", 0)
            row.group_credit_total = summary.get("credit_total", 0)
        # > Keep the enriched rows so the inline template can read summary values.
        qs_cache = cast(Any, qs)
        qs_cache._result_cache = rows
        qs_cache._prefetch_done = True
        return qs

    @admin.display(description="Students", ordering="student_total")
    def student_count_link(self, obj):
        """Link to students enrolled in this curriculum course."""
        count = getattr(obj, "student_total", None)
        if count is None:
            count = (
                obj.sections.filter(section_registrations__student__isnull=False)
                .values_list("section_registrations__student_id", flat=True)
                .distinct()
                .count()
            )
        url = reverse("admin:people_student_changelist") + (
            f"?student_registrations__section__curriculum_course__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)


class DepartmentCourseInline(admin.TabularInline):
    """Inline courses of a department."""

    model = Course
    fk_name = "department"
    verbose_name_plural = "Courses offered by this department "
    extra = 0
    autocomplet_fields = ("course",)
    fields = ("short_code", "number", "title")
    ordering = ("short_code",)
