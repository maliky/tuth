# app/admin/inlines.py
from django.contrib import admin
from app.models import Semester, Section, Prerequisite


class SemesterInline(admin.TabularInline):
    model = Semester
    extra = 0
    max_num = 3
    fields = ("number", "start_date", "end_date")
    ordering = ("start_date",)


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0
    fields = ("number", "semester", "instructor", "room", "max_seats")
    ordering = ("semester__starting_date", "number")


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
