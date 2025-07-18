"""Inlines for the registry admin interface."""

from django.contrib import admin

from app.registry.models.grade import Grade


class GradeInline(admin.TabularInline):
    """Inline editor for Grade records in a section."""

    model = Grade
    fk_name = "section"
    extra = 0
    fields = ("student", "grade", "graded_on")
    readonly_fields = ("graded_on",)
    autocomplete_fields = ("student",)
