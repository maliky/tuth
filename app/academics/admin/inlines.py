"""Inlines module."""

from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from app.academics.models.prerequisite import Prerequisite
from app.academics.models.course import Course
from app.academics.models.curriculum_course import CurriculumCourse


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


class CurriculumCourseInline(admin.TabularInline):
    """Inline for linking courses to a curriculum."""

    model = CurriculumCourse
    fk_name = "curriculum"
    verbose_name_plural = "Courses in this curriculum."
    extra = 0
    autocomplete_fields = ("course", "curriculum")
    ordering = ("course",)
    fields = (
        "course",
        "credit_hours",
        "is_required",
        "is_elective",
        "student_count_link",
    )
    readonly_fields = ("student_count_link",)

    def get_queryset(self, request):
        """Annotate student totals for curriculum-course rows."""
        qs = super().get_queryset(request)
        return qs.annotate(
            student_total=Count("sections__section_registrations__student", distinct=True)
        )

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
