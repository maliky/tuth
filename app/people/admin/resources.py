"""Resources module."""

from import_export import fields, resources
from django.contrib.auth.models import Group
from app.people.choices import UserRole

from app.people.admin.widgets import StaffProfileWidget, StudentUserWidget
from app.people.models.staffs import Faculty, Staff
from app.people.models.student import Student
from app.people.utils import mk_username, split_name
from app.registry.models.registration import Registration
from app.timetable.admin.widgets.core import SemesterWidget


class DirectoryContactResource(resources.ModelResource):
    """Import staff directory rows and create/update Staff profiles."""

    username = fields.Field(column_name="username", attribute="user__username")
    first_name = fields.Field(column_name="first_name", attribute="user__first_name")
    last_name = fields.Field(column_name="last_name", attribute="user__last_name")
    middle_name = fields.Field(column_name="middle_name", attribute="middle_name")
    name_prefix = fields.Field(column_name="name_prefix", attribute="name_prefix")
    name_suffix = fields.Field(column_name="name_suffix", attribute="name_suffix")

    class Meta:
        model = Staff
        import_id_fields = ("user__username",)
        fields = (
            "username",
            "first_name",
            "last_name",
            "middle_name",
            "name_prefix",
            "name_suffix",
        )
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        """Get the faculty name and populate the username if empty."""
        raw_name = (row.get("faculty") or row.get("name") or "").strip()
        prefix, first, middle, last, suffix = split_name(raw_name)
        row.update(
            {
                "name_prefix": prefix,
                "first_name": first,
                "middle_name": middle,
                "last_name": last,
                "name_suffix": suffix,
            }
        )
        if not row.get("username"):
            row["username"] = mk_username(first, last, unique=True)


class FacultyResource(resources.ModelResource):
    """Import-Export Faculty staff.

    CSV columns:
    faculty        :long display name (“Dr. Jane A. Doe PhD”…)
    college_code   :optional – defaults to “COAS”
    """

    staff_profile = fields.Field(
        attribute="staff_profile",
        column_name="faculty",
        widget=StaffProfileWidget(),
    )

    class Meta:
        model = Faculty
        import_id_fields = ("staff_profile",)
        fields = "staff_profile"
        skip_unchanged = True
        report_skipped = False

    def after_save_instance(self, instance, row, **kwargs) -> None:
        """Assign the faculty group to the related user."""
        if kwargs.get("dry_run"):
            return None

        user = instance.staff_profile.user
        group, _ = Group.objects.get_or_create(name=UserRole.FACULTY.label)
        user.groups.add(group)


class StudentResource(resources.ModelResource):
    """Resource for bulk importing Student rows."""

    # should populate the pk field directly
    user = fields.Field(
        attribute="user", column_name="student_name", widget=StudentUserWidget()
    )

    current_enroled_semester = fields.Field(
        attribute="current_enroled_semester",
        column_name="semester_no",
        widget=SemesterWidget(),
    )

    class Meta:
        model = Student
        import_id_fields = ("student_id",)
        fields = (
            "student_id",
            "user",
            "curriculum",
            "current_enroled_semester",
            "first_enrollement_date",
        )

    def after_save_instance(self, instance, row, **kwargs) -> None:
        """Assign the student group to the user when importing."""
        if kwargs.get("dry_run") or instance.user is None:
            return

        group, _ = Group.objects.get_or_create(name=UserRole.STUDENT.label)
        instance.user.groups.add(group)


class RegistrationResource(resources.ModelResource):
    """Resource for bulk importing :class:Registration rows."""

    class Meta:
        model = Registration
        import_id_fields = ("student", "section")
        fields = (
            "student",
            "section",
            "status",
        )
