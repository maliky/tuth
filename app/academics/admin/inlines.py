from django.contrib import admin

from app.academics.models import Prerequisite, CurriculumCourse


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


class CurriculumCourseInline(admin.TabularInline):
    model = CurriculumCourse
    extra = 0
    autocomplete_fields = ("course",)
    ordering = ("year_level", "semester_no")
