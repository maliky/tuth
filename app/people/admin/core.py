"""Core module."""

from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.people.models import DonorProfile, FacultyProfile, StudentProfile


@admin.register(StudentProfile)
class StudentProfileAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for :class:`~app.people.models.StudentProfile`."""
    list_display = ("student_id", "user", "college", "curriculum")
    search_fields = (
        "student_id",
        "user__username",
        "user__first_name",
        "user__last_name",
    )
    # > add an inlines to list the current course of the students = []
    # > add an inlines to list the passed course of the students = []
    list_filter = ("college", "curriculum")
    autocomplete_fields = ("user", "college", "curriculum")


@admin.register(FacultyProfile)
class FacultyProfileAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin options for :class:`~app.people.models.FacultyProfile`."""
    list_display = ("user", "division", "department", "college", "position")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
    )
    # not sure to be able to use curricula which is a computed property
    list_filter = ("college", "position")
    autocomplete_fields = (
        "user",
        "college",
    )


@admin.register(DonorProfile)
class DonorProfileAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin management for :class:`~app.people.models.DonorProfile`."""
    list_display = ("user", "donor_id")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "donor_id",
    )
    autocomplete_fields = ("user",)
