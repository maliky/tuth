"""Inlines for the registry admin interface."""

from django.contrib import admin

from app.registry.models.grade import Grade


class GradeInline(admin.TabularInline):
    """Inline editor for :class:`~app.registry.models.Grade` records."""

    model = Grade
    fk_name = "section"
    extra = 0
    fields = ("student", "letter_grade", "numeric_grade", "graded_on")
    readonly_fields = ("graded_on",)
    autocomplete_fields = ("student",)
