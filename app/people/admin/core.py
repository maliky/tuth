"""Core module."""

from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from import_export.admin import ImportExportModelAdmin

from app.people.admin.resources import FacultyResource
from app.people.forms.base import PersonFormMixin
from app.people.forms.faculty import FacultyForm
from app.people.forms.person import (
    DonorForm,
    StaffForm,
    StudentForm,
)
from app.people.models.donor import Donor
from app.people.models.staffs import Faculty, Staff
from app.people.models.student import Student
from app.shared.admin.mixins import CollegeRestrictedAdmin, DepartmentRestrictedAdmin
from app.timetable.admin.inlines import SectionInline


@admin.register(Faculty)
class FacultyAdmin(CollegeRestrictedAdmin, ImportExportModelAdmin, GuardedModelAdmin):
    """Admin options for :class:~app.people.models.Faculty.

    Displays the staff profile with optional filtering by college. The faculty
    resource is used for import/export operations.
    """

    # form =
    resource_class = FacultyResource
    form = FacultyForm

    list_display = (
        "faculty_name",
        "faculty_staff_id",
        "academic_rank",
        "get_division",
        "get_department",
    )
    list_filter = ("college",)
    search_fields = ("faculty_staff_id", "faculty_name", "faculty_academic_rank")
    autocomplete_fields = ("staff_profile", "college")
    inlines = [SectionInline]
    fieldsets = [
        (
            "User Information",
            {
                "fields": FacultyForm.USER_FIELDS,
                "description": (
                    "Username / e-mail are auto-generated from the name fields. "
                    "To change the password you need to open the user box."
                ),
            },
        ),
        ("Faculty Information", {"fields": FacultyForm.FACULTY_FIELDS}),
        (
            "Work Information",
            {
                "classes": ["collapse"],
                "fields": FacultyForm.STAFF_FIELDS,
            },
        ),
    ]

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

    form = DonorForm
    list_display = ("user", "donor_id")
    search_fields = ("donor_id", "user__long_name")
    readonly_fields = ("donor_id",)
    fieldsets = [
        (
            "User Account",
            {
                "classes": ["collapse"],
                "fields": PersonFormMixin.USER_FIELDS,
                "description": (
                    "Username / e-mail are auto-generated from the name fields. "
                    "To change the password you need to open the user box."
                ),
            },
        ),
        (None, {"fields": PersonFormMixin.STANDARD_USER_FIELDS}),
    ]


@admin.register(Staff)
class StaffAdmin(DepartmentRestrictedAdmin, GuardedModelAdmin):
    """Admin management for :class:~app.people.models.Staff.

    Provides detailed fieldsets for personal and work information. Important
    fields like staff_id are read-only to avoid accidental edits.
    """

    form = StaffForm
    list_display = ("long_name", "staff_id", "position", "roles")
    search_fields = ("staff_id", "username", "long_name", "department")
    list_filter = ("department",)
    readonly_fields = ("staff_id",)
    fieldsets = [
        (
            "User Account",
            {
                "fields": PersonFormMixin.USER_FIELDS,
                "description": (
                    "Username / e-mail are auto-generated from the name fields. "
                    "To change the password you need to open the user box."
                ),
            },
        ),
        ("Personal Details", {"fields": PersonFormMixin.STANDARD_USER_FIELDS}),
        (
            "Work Information",
            {
                "classes": ["collapse"],
                "fields": StaffForm.SPECIFIC_FIELDS,
            },
        ),
    ]


@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin, GuardedModelAdmin):
    """Admin interface for :class:~app.people.models.Student.

    list_display shows the related user and student ID with search enabled
    on both fields. Import/export is supported via ImportExportModelAdmin.
    """

    form = StudentForm
    list_display = ("long_name", "student_id", "date_of_birth")
    search_fields = ("student_id", "username", "long_name")
    readonly_fields = ("student_id",)
    fieldsets = [
        (
            "Student Informations",
            {
                "fields": StudentForm.SPECIFIC_FIELDS,
            },
        ),
        (
            "User Account",
            {
                "classes": ["collapse"],
                "fields": PersonFormMixin.USER_FIELDS,
                "description": (
                    "Username / e-mail are auto-generated from the name fields. "
                    "To change the password you need to open the user box."
                ),
            },
        ),
        (
            "User Details",
            {"classes": ["collapse"], "fields": PersonFormMixin.STANDARD_USER_FIELDS},
        ),
    ]

    # -------------- helpers for readonly panel --------------
    def save_model(self, request, obj, form, change):
        """Save the model."""
        # The form.save() handles creating and linking the User.
        obj.save()
