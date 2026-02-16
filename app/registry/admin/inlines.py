"""ILs for the registry admin interface."""

from app.registry.models.document import DocStd, DocStaff, DocDonor
from django.contrib import admin
from django.db.models import Prefetch
from django.urls import reverse
from django.utils.html import format_html

from app.registry.models.grade import Grade
from app.registry.models.registration import Registration


def _format_sec_link(section) -> str:
    """Return a link to the section change view."""
    if not section:
        return "-"
    url = reverse("admin:timetable_section_change", args=[section.pk])
    return format_html('<a href="{}">{}</a>', url, section)


def _format_sec_sem(section):
    """Return the semester label for a section."""
    if not section:
        return "-"
    return section.semester


class GradeIL(admin.TabularInline):
    """Inline editor for Grade records in a section."""

    model = Grade
    classes = ["collapse"]
    fk_name = "section"
    extra = 0
    fields = ("student", "value", "graded_on")
    readonly_fields = ("graded_on",)
    autocomplete_fields = ("student",)


class StdRegistrationIL(admin.TabularInline):
    """Inline list of student registrations with grade summaries."""

    model = Registration
    classes = ["collapse"]
    fk_name = "student"
    verbose_name = "Currently registered sections"
    extra = 0
    # Allow staff to remove registrations directly from the student admin.
    can_delete = True
    fields = ("section_link", "section_semester", "status", "grade_code")
    readonly_fields = ("section_link", "section_semester", "grade_code")

    def get_queryset(self, request):
        """Annotate registrations with grade codes for display."""
        qs = super().get_queryset(request).select_related("section__semester")
        # Avoid Subquery/OuterRef so mypy stays stable; use prefetch + in-memory match.
        grade_qs = Grade.objects.select_related("value")
        return qs.prefetch_related(Prefetch("section__grade_set", queryset=grade_qs))

    @admin.display(description="Section")
    def section_link(self, obj):
        """Link to the related section change page."""
        return _format_sec_link(obj.section)

    @admin.display(description="Semester")
    def section_semester(self, obj):
        """Show the semester for the linked section."""
        return _format_sec_sem(obj.section)

    @admin.display(description="Grade")
    def grade_code(self, obj):
        """Display the grade code for the registration, if any."""
        grades = getattr(obj.section, "grade_set", None)
        if not grades:
            return "-"
        grade = next(
            (item for item in grades.all() if item.student_id == obj.student_id),
            None,
        )
        if not grade or not grade.value:
            return "-"
        code = grade.value.code or ""
        return code.upper() if code else "-"


class StdGradeIL(admin.TabularInline):
    """Inline list of grades attached to a student."""

    model = Grade
    classes = ["collapse"]
    fk_name = "student"
    verbose_name = "Grade"
    verbose_name_plural = "Grades by course level"
    extra = 0
    classes = ["collapse"]
    can_delete = False
    fields = ("section_link", "value")
    readonly_fields = ("section_link", "value")
    template = "admin/registry/studentgrade/tabular_inline.html"

    def get_queryset(self, request):
        """Select related data and sort rows so levels stay grouped."""
        qs = super().get_queryset(request)
        # Keep a stable order so template groups by semester + level.
        return qs.select_related(
            "section__semester",
            "section__curriculum_course__course",
            "value",
        ).order_by(
            "-section__semester__start_date",
            "-section__semester__number",
            "section__curriculum_course__level_number",
            "section__curriculum_course__course__short_code",
            "section__number",
        )

    @admin.display(description="Section")
    def section_link(self, obj):
        """Link to the related section change page."""
        return _format_sec_link(obj.section)


class DocStaffIL(admin.TabularInline):  # StackedIL
    model = DocStaff
    classes = ["collapse"]
    can_delete = True


class DocStdIL(admin.TabularInline):  # StackedIL
    model = DocStd
    classes = ["collapse"]
    can_delete = True


class DocDonorIL(admin.TabularInline):  # StackedIL
    model = DocDonor
    classes = ["collapse"]
    can_delete = True
