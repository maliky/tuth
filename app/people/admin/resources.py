"""Resources module."""

from import_export import fields, resources

from app.people.admin.widgets import UserWidget
from app.people.models import StudentProfile
from app.people.models.profile import FacultyProfile
from app.registry.models import Registration

# ? should I have a User Ressource class and extand the profile from it ?


class FacultyResource(resources.ModelResource):
    """Resource for bulk importing :class:`FacultyProfile` rows"""

    user = fields.Field(
        column_name="faculty",
        attribute="user",
        widget=UserWidget(),
    )

    class Meta:
        model = FacultyProfile
        fields = (
            "staff_id"
            "college",
            "name_prefix",
            "name_suffix",
            "middle_name",
            "first_name",
            "last_name"
            "username"
        )


class StudentResource(resources.ModelResource):
    """Resource for bulk importing :class:`StudentProfile` rows."""

    class Meta:
        model = StudentProfile
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
    """Resource for bulk importing :class:`Registration` rows."""

    class Meta:
        model = Registration
        import_id_fields = ("student", "section")
        fields = (
            "student",
            "section",
            "status",
            "date_latest_reservation",
        )
