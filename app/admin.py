from django.contrib import admin
from guardian.admin import GuardedModelAdmin  # enables object perms UI
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from app.models import (
    College,
    Curriculum,
    Course,
)


class CurriculumResource(resources.ModelResource):
    class Meta:
        model = Curriculum
        # specify fields order or exclude if needed
        fields = (
            "id",
            "title",
            "level",
            "academic_year",
            "college__code",
            "validation_status",
            "is_active",
        )


@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ("code", "fullname", "current_dean")


@admin.register(Curriculum)
class CurriculumAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = CurriculumResource
    list_display = ("title", "level", "academic_year", "college", "is_active")
    list_filter = ("college", "level", "academic_year", "is_active")
    search_fields = ("title",)


class CourseInline(admin.TabularInline):
    model = Course
    extra = 0


class CourseResource(resources.ModelResource):
    class Meta:
        model = Course
        exclude = ("description",)  # example: omit long text if not needed


@admin.register(Course)
class CourseAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_class = CourseResource
    list_display = ("code", "title", "curriculum", "credit_hours")
    list_filter = ("curriculum__college", "curriculum__academic_year")
    search_fields = ("code", "title")
