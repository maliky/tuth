"""Resources module."""

from app.people.models import StudentProfile
from app.registry.models import Registration

from import_export import resources

class FacultyResource(resources.ModelResource):
    """Resource for bulk importing :class:`FacultyProfile` rows"""
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
