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
    fields = [
        "staff_profile",
        "college",
        "google_profile",
        "personal_website",
        "academic_rank",
    ]

    list_display = ("staff_profile",)
    list_filter = ("college",)
    search_fields = (
        "staff_profile__staff_id",
        "staff_profile__user__username",
        "staff_profile__user__full_name",
    )
    autocomplete_fields = ("staff_profile",)

    def get_fields(self, request, obj=None):
        """
        override the function getting the fields from the model
        without rewriting them all. but the one I want to promote in 'front'
        """
        all_fields = super().get_fields(request, obj)
        # ensure these come first, in this order:
        # front = ['staff_profile__long_name', 'staff_profile__staff_id']
        front: list[str] = [""]
        # remove them from the master list and re-insert at front
        rest = [f for f in all_fields if f not in front]
        return front + rest


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
            "Personnal Info",
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
    )
    list_display = (
        "long_name",
        "user",
        "staff_id",
    )
    search_fields = (
        "staff_id",
        "user__username",
        "long_name",
    )
    autocomplete_fields = ("user",)
    readonly_fields = ("staff_id", "long_name", "age")


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
