"""Core module."""

from app.people.admin.resources import FacultyResource
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.academics.admin.filters import CurriculumFilter
from app.people.models import Donor, Faculty, Student


@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for :class:`~app.people.models.Student`."""

    list_display = ("student_id", "user", "college", "curriculum")
    search_fields = (
        "student_id",
        "user__username",
        "user__first_name",
        "user__last_name",
    )
    # > add an inlines to list the current course of the students = []
    # > add an inlines to list the passed course of the students = []
    list_filter = ("college", CurriculumFilter)
    autocomplete_fields = ("user", "college", "curriculum")


@admin.register(Faculty)
class FacultyAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin options for :class:`~app.people.models.Faculty`."""

    resource_classes = FacultyResource
    list_display = ("staff_profile", "college", "academic_rank")
    autocomplete_fields = ("staff_profile", "college")
    search_fields = ("last_name", "first_name")
    list_filter = "college"


@admin.register(Donor)
class DonorAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin management for :class:`~app.people.models.Donor`."""

    list_display = ("user", "donor_id")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "donor_id",
    )
    autocomplete_fields = ("user",)
