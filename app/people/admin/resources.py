"""Resources module."""

from import_export import fields, resources

from app.people.admin.widgets import StaffProfileWidget
from app.people.models.staffs import Faculty, Staff
from app.people.models.student import Student
from app.people.utils import mk_username, split_name
from app.registry.models.registration import Registration


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
        row["name_prefix"] = prefix
        row["first_name"] = first
        row["middle_name"] = middle
        row["last_name"] = last
        row["name_suffix"] = suffix
        if not row.get("username"):
            row["username"] = mk_username(first, last, unique=True)


class FacultyResource(resources.ModelResource):
    """Expected CSV columns.

    faculty        ← long display name (“Dr. Jane A. Doe PhD”…)
    college_code   ← optional – defaults to “COAS”
    """

    staff_profile = fields.Field(
        column_name="faculty",
        attribute="staff_profile",
        widget=StaffProfileWidget(),
    )

    class Meta:
        model = Faculty
        import_id_fields = ("staff_profile",)
        fields = "staff_profile"
        skip_unchanged = True
        report_skipped = False


class StudentResource(resources.ModelResource):
    """Resource for bulk importing :class:Student rows."""

    class Meta:
        model = Student
        import_id_fields = ("student_id",)
        fields = (
            "student_id",
            "user",
            "college",
            "curriculum",
            "enrollment_semester",
            "enrollment_date",
        )


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
