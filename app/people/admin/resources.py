"""Resources module."""

from import_export import fields, resources
from import_export.widgets import DateTimeWidget
from app.academics.admin.widgets import CurriculumWidget
from app.shared.auth.perms import UserRole

from app.people.admin.widgets import StaffProfileWidget, UserStudentWidget
from app.people.models.staffs import Staff
from app.people.models.faculty import Faculty
from app.people.models.student import Student
from app.people.utils import mk_username, split_name
from app.registry.models.registration import Registration
from app.timetable.admin.widgets.core import SemesterCodeWidget


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
        fields = ("staff_profile",)
        skip_unchanged = True
        report_skipped = False
        use_bulk = True

    def after_save_instance(self, instance, row, **kwargs):
        """Assign the faculty group to the related user."""
        if kwargs.get("dry_run"):
            return None

        user = instance.staff_profile.user
        group = UserRole.FACULTY.value.group
        user.groups.add(group)

        return super().after_save_instance(instance, row, **kwargs)


class StudentResource(resources.ModelResource):
    """Resource for bulk importing Student rows."""

    # I only see Long_name student ID and date of birth
    # Should populate the pk field directly
    user = fields.Field(
        attribute="user", column_name="student_name", widget=UserStudentWidget()
    )

    current_enrolled_semester = fields.Field(
        attribute="current_enrolled_semester",
        column_name="current_enrolled_sem",
        widget=SemesterCodeWidget(),
    )
    entry_semester = fields.Field(
        attribute="entry_semester",
        column_name="entry_semester",
        widget=SemesterCodeWidget(),
    )
    curriculum = fields.Field(
        attribute="curriculum", column_name="major", widget=CurriculumWidget()
    )

    # ~~~~~~~~~~~~~~~~ demographic fields ~~~~~~~~~~~~~~~~~

    birth_date = fields.Field(
        attribute="birth_date",
        column_name="birth_date",
        widget=DateTimeWidget("%Y-%m-%d %H:%M:%S"),
    )
    # marital_status = fields.Field(
    #     attribute="marital_status",
    #     column_name="marital_status",
    # )
    # nationality = fields.Field(attribute="nationality", column_name="nationality")
    # gender = fields.Field(attribute="gender", column_name="gender")

    class Meta:
        model = Student
        import_id_fields = ("student_id",)
        fields = (
            "student_id",
            "user",
            "curriculum",
            "current_enrolled_semester",
            "entry_semester",
            "nationality",
            "birth_date",
            "marital_status",
            "gender",
        )
        skip_unchanged = True
        report_skipped = False
        use_bulk = False  # do not use because ressources is down row by row

    def do_instance_save(self, instance, is_create) -> None:
        """Overide the instance save operation."""
        instance.save()
        pass

    def before_save_instance(self, instance, row, **kwargs) -> None:
        """Overide operation juste before save."""
        # import ipdb; ipdb.set_trace()
        pass

    def after_save_instance(self, instance, row, **kwargs) -> None:
        """Assign the student group to the user when importing."""
        if kwargs.get("dry_run") or instance.user is None:
            return
        # group = UserRole.STUDENT.value.group
        # instance.user.groups.add(group)
        # import ipdb; ipdb.set_trace()
