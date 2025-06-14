"""Core module."""

from app.people.admin.resources import FacultyResource
from app.people.models.others import Donor, Student
from app.people.models.staffs import Faculty, Staff
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin


@admin.register(Faculty)
class FacultyAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin options for :class:`~app.people.models.Faculty`."""

    resource_classes = FacultyResource
    list_display = ("staff_profile", "college")
    search_fields = (
        "staff_profile__staff_id",
        "staff_profile__user__username",
        "staff_profile__user__full_name",
    )
    autocomplete_fields = ("staff_profile",)


@admin.register(Donor)
class DonorAdmin(GuardedModelAdmin):
    """Admin management for :class:`~app.people.models.Donor`."""

    list_display = ("user", "donor_id")
    search_fields = (
        "donor_id",
        "user__username",
        "user__full_name",
    )
    autocomplete_fields = ("user",)


@admin.register(Staff)
class StaffAdmin(GuardedModelAdmin):
    """Admin management for :class:`~app.people.models.Staff`."""

    list_display = ("user", "staff_id")
    search_fields = (
        "staff_id",
        "user__username",
        "user__full_name",
    )
    autocomplete_fields = ("user",)


@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for :class:`~app.people.models.Student`."""

    list_display = ("user", "student_id")
    search_fields = (
        "student_id",
        "user__username",
        "user__full_name",
    )
    autocomplete_fields = ("user",)
