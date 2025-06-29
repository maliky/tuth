"""Core module."""

from app.people.admin.resources import FacultyResource
from app.people.models.student import Student
from app.people.models.donor import Donor
from app.people.models.staffs import Faculty, Staff
from app.timetable.admin.inlines import SectionInline
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
    list_display = (
        "faculty_name",
        "faculty_staff_id",
    )
    list_filter = ("college",)
    search_fields = ("faculty_staff_id", "faculty_name")
    autocomplete_fields = ("staff_profile",)
    inlines = [SectionInline]

    @admin.display(description="Long Name", ordering="staff_profile__user__first_name")
    def faculty_name(self, obj):
        """Add the long name to the admin."""
        return obj.staff_profile.long_name

    @admin.display(description="Faculty Staff ID", ordering="staff_profile__staff_id")
    def faculty_staff_id(self, obj):
        """Add the long name to the admin."""
        return obj.staff_profile.staff_id


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

    fields = (
        "user",
        "staff_id",
        "photo",
        "name_prefix",
        "middle_name",
        "name_suffix",
        "phone_number",
        "physical_address",
        "date_of_birth",
        "bio",
        "employment_date",
        "division",
        "department",
        "position",
    )
    list_display = (
        "long_name",
        "staff_id",
    )
    search_fields = ("staff_id",)
    autocomplete_fields = ("user",)
    readonly_fields = ("staff_id", "age")


@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for :class:~app.people.models.Student.

    list_display shows the related user and student ID with search enabled
    on both fields. Import/export is supported via ImportExportModelAdmin.
    """

    list_display = ("long_name", "student_id", "user")
    search_fields = (
        "student_id",
        "user__username",
        # "long_name"
        # "user__first_name",
        # "user__last_name",
    )
    autocomplete_fields = ("user",)
