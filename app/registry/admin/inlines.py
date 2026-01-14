"""Inlines for the registry admin interface."""

from app.registry.models.document import DocumentStudent, DocumentStaff, DocumentDonor
from django.contrib import admin
from django.db.models import Prefetch
from django.urls import reverse
from django.utils.html import format_html

from app.registry.models.grade import Grade
from app.registry.models.registration import Registration


class GradeInline(admin.TabularInline):
    """Inline editor for Grade records in a section."""

    model = Grade
    fk_name = "section"
    extra = 0
    fields = ("student", "value", "graded_on")
    readonly_fields = ("graded_on",)
    autocomplete_fields = ("student",)


class StudentRegistrationInline(admin.TabularInline):
    """Inline list of student registrations with grade summaries."""

    model = Registration
    fk_name = "student"
    extra = 0
    can_delete = False
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
        section = obj.section
        url = reverse("admin:timetable_section_change", args=[section.pk])
        return format_html('<a href="{}">{}</a>', url, section)

    @admin.display(description="Semester")
    def section_semester(self, obj):
        """Show the semester for the linked section."""
        if not obj.section_id:
            return "-"
        return obj.section.semester

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


class DocumentStaffInline(admin.TabularInline):  # StackedInline
    model = DocumentStaff
    can_delete = True


class DocumentStudentInline(admin.TabularInline):  # StackedInline
    model = DocumentStudent
    can_delete = True


class DocumentDonorInline(admin.TabularInline):  # StackedInline
    model = DocumentDonor
    can_delete = True
