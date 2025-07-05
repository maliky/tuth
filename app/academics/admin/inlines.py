"""Inlines module."""

from django.contrib import admin

from app.academics.models.prerequisite import Prerequisite
from app.academics.models.program import Program


class RequiresInline(admin.TabularInline):
    """Inline editor for Prerequisite needed by a course."""

    model = Prerequisite
    fk_name = "course"
    verbose_name_plural = "Prerequisites this course needs"
    extra = 0
    autocomplete_fields = ("prerequisite_course",)


class PrerequisiteInline(admin.TabularInline):
    """Inline showing courses that depend on the current course."""

    model = Prerequisite
    fk_name = "prerequisite_course"
    verbose_name_plural = "Courses that require this course"
    extra = 0
    autocomplete_fields = ("course",)


class CourseProgramInline(admin.TabularInline):
    """Inline for linking courses to a program."""

    model = Program
    fk_name = "course"
    verbose_name_plural = "Curricula with this course."
    extra = 0
    autocomplete_fields= ('curriculum',)

class CurriculumProgramInline(admin.TabularInline):
    """Inline for linking courses to a program."""

    model = Program
    fk_name = "curriculum"
    verbose_name_plural = "Courses in this curriculum."
    extra = 0
    autocomplete_fields = ("course",)


# class CourseProgramInline(admin.TabularInline):
#     """Inline for linking programs to a course."""

#     model = Program
#     fk_name = "curriculum"
#     verbose_name_plural = "Courses in this program."
#     extra = 0
#     # autocomplete_fields = ("curriculum",)
