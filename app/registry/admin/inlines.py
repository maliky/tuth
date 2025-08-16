"""Inlines for the registry admin interface."""

from app.registry.models.document import DocumentStudent, DocumentStaff, DocumentDonor
from django.contrib import admin

from app.registry.models.grade import Grade


class GradeInline(admin.TabularInline):
    """Inline editor for Grade records in a section."""

    model = Grade
    fk_name = "section"
    extra = 0
    fields = ("student", "value", "graded_on")
    readonly_fields = ("graded_on",)
    autocomplete_fields = ("student",)


class DocumentStaffInline(admin.TabularInline):  # StackedInline
    model = DocumentStaff
    can_delete = True


class DocumentStudentInline(admin.TabularInline):  # StackedInline
    model = DocumentStudent
    can_delete = True


class DocumentDonorInline(admin.TabularInline):  # StackedInline
    model = DocumentDonor
    can_delete = True
