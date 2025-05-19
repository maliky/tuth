# app/admin/college_admin.py
from django import forms
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.models import College, Course, Curriculum, Prerequisite
from app.constants.choices import CREDIT_CHOICES

from .inlines import PrerequisiteInline, RequiresInline, SectionInline, CurriculaInline
from .resources import CourseResource, CurriculumResource, PrerequisiteResource

from app.admin.filters import CurriculumFilter


@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ("code", "fullname", "current_dean")
    search_fields = ("code", "fullname")


@admin.register(Curriculum)
class CurriculumAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = CurriculumResource
    list_display = ("college", "title", "short_name", "creation_date", "is_active")
    list_filter = ("college", "short_name", "is_active")
    autocomplete_fields = ("college", "creation_date")
    list_select_related = (
        "creation_date",
        "college",
    )
    search_fields = ("title",)


class CourseForm(forms.ModelForm):
    credit_hours = forms.TypedChoiceField(
        coerce=int,
        choices=CREDIT_CHOICES.choices,
        empty_value=None,  # show blank to type anything
        widget=forms.NumberInput(attrs={"min": 1}),  # numeric input
    )

    class Meta:
        model = Course
        fields = "__all__"


@admin.register(Course)
class CourseAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = CourseResource
    list_display = ("code", "title", "credit_hours")
    list_filter = ("curricula__college", "curricula")
    autocomplete_fields = ("curricula",)
    inlines = [SectionInline, PrerequisiteInline, RequiresInline, CurriculaInline]
    list_select_related = ("college",)

    search_fields = ("code", "title")
    form = CourseForm
    fieldsets = (
        (None, {"fields": ("name", "number", "title", "credit_hours", "curricula")}),
        (
            "Additional details",
            {
                "classes": ("collapse",),
                "fields": ("description",),
            },
        ),
    )


@admin.register(Prerequisite)
class PrerequisiteAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    resource_class = PrerequisiteResource
    list_display = ("curriculum", "course", "prerequisite_course")
    autocomplete_fields = ("curriculum", "course", "prerequisite_course")
    list_filter = (CurriculumFilter,)
