"""Resources module."""

from django.contrib.auth.models import User
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
        widget=UserWidget(
            model=User, field="faculty"
        ),  # not sure about the field value here.
    )

    class Meta:
        model = FacultyProfile
        fields = (
            "user",
            "college",
            "curriculum",
            "enrollment_semester",
            "enrollment_date",
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
