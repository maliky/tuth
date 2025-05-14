# app/admin/inlines.py
from django.contrib import admin
from app.models import Term, Section, Prerequisite


class TermInline(admin.TabularInline):
    model = Term
    extra = 0
    max_num = 3
    fields = ("number", "start_date", "end_date")
    ordering = ("number",)


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0
    fields = ("number", "term", "instructor", "room", "max_seats")
    ordering = ("term__academic_year__starting_date", "term__number", "number")


class RequiresInline(admin.TabularInline):
    model = Prerequisite
    fk_name = "course"
    verbose_name_plural = "Prerequisites this course needs"
    extra = 0
    autocomplete_fields = ("prerequisite_course",)


class PrerequisiteInline(admin.TabularInline):
    model = Prerequisite
    fk_name = "prerequisite_course"
    verbose_name_plural = "Courses that require this course"
    extra = 0
    autocomplete_fields = ("course",)
