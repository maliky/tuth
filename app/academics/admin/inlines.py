"""Inlines module."""

from django.contrib import admin

from app.academics.models.prerequisite import Prerequisite
from app.academics.models.course import CurriculumCourse, Course


class RequiresInline(admin.TabularInline):
    """Inline editor for Prerequisite needed by a course."""

    model = Prerequisite
    fk_name = "course"
    verbose_name_plural = "Prerequisites this course needs"
    extra = 0
    autocomplete_fields = ("prerequisite_course",)
    ordering =("prerequisite_course",)

class PrerequisiteInline(admin.TabularInline):
    """Inline showing courses that depend on the current course."""

    model = Prerequisite
    fk_name = "prerequisite_course"
    verbose_name_plural = "Courses that require this course"
    extra = 0
    autocomplete_fields = ("course",)
    ordering =("course",)

class CourseCurriculumInline(admin.TabularInline):
    """Inline for linking  curriculum to course."""

    model = CurriculumCourse
    fk_name = "course"
    verbose_name_plural = "Curricula with this course."
    extra = 0
    autocomplete_fields = ("curriculum",)
    ordering =("course",)

class CurriculumCourseInline(admin.TabularInline):
    """Inline for linking courses to a curriculum."""

    model = CurriculumCourse
    fk_name = "curriculum"
    verbose_name_plural = "Courses in this curriculum."
    extra = 0
    autocomplete_fields = ("course","curriculum")
    ordering =("course",)
    
class DepartmentCourseInline(admin.TabularInline):
    """Inline courses of a department."""

    model = Course
    fk_name = "department"
    verbose_name_plural = "Courses offered by this department "
    extra = 0
    autocomplet_fields = ("course",)
    fields = ("short_code", "number", "title")
    ordering =("short_code",)
