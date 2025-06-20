"""Core module."""

from app.people.admin.resources import FacultyResource
from app.people.models.student import Student
from app.people.models.donor import Donor
from app.people.models.staffs import Faculty, Staff
from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin


@admin.register(Faculty)
class FacultyAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin options for :class:~app.people.models.Faculty.

    Displays the staff profile with optional filtering by college. The faculty
    resource is used for import/export operations.
    """

    resource_class = FacultyResource
    fields = (
        "staff_profile",
        "college",
        "academic_rank",
        "google_profile",
        "personal_website",
    )

    list_display = ("staff_profile",)
    list_filter = ("college",)
    search_fields = (
        "staff_profile__staff_id",
        "staff_profile__username",
        "staff_profile__first_name",
        "staff_profile__last_name",
    )
    autocomplete_fields = ("staff_profile",)


@admin.register(Donor)
class DonorAdmin(GuardedModelAdmin):
    """Admin management for :class:~app.people.models.Donor.

    Shows each donor's user and ID with autocomplete for the user relation.
    """

    list_display = ("user", "donor_id")
    search_fields = (
        "donor_id",
        "user__username",
        "user__first_name",
        "user__last_name",
    )
    autocomplete_fields = ("user",)


@admin.register(Staff)
class StaffAdmin(GuardedModelAdmin):
    """Admin management for :class:~app.people.models.Staff.

    Provides detailed fieldsets for personal and work information. Important
    fields like staff_id are read-only to avoid accidental edits.
    """

    # ▸ custom helper so list_display works with M2M

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "long_name",
                    "staff_id",
                    "user",
                ),
            },
        ),
        (
            "Personal Info",
            {
                "fields": (
                    "photo",
                    "name_prefix",
                    "middle_name",
                    "name_suffix",
                    "phone_number",
                    "physical_address",
                    "date_of_birth",
                    "bio",
                ),
                #                "classes": ("collapse",),
            },
        ),
        (
            "Work Info",
            {
                "fields": (
                    "employment_date",
                    "division",
                    "department",
                    "position",
                ),
            },
        ),
    )
    list_display = (
        "long_name",
        "user",
        "staff_id",
        "department",
    )
    search_fields = (
        "staff_id",
        "user__username",
        "long_name",
        "department",
    )
    autocomplete_fields = ("user", "department")
    readonly_fields = ("staff_id", "long_name", "age")


@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for :class:~app.people.models.Student.

    list_display shows the related user and student ID with search enabled
    on both fields. Import/export is supported via ImportExportModelAdmin.
    """

    list_display = ("user", "student_id")
    search_fields = (
        "student_id",
        "user__username",
        "user__first_name",
        "user__last_name",
    )
    autocomplete_fields = ("user",)
