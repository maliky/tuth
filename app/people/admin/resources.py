"""Resources module."""

from import_export import fields, resources

from app.academics.admin.widgets import CollegeWidget
from app.people.admin.widgets import StaffProfileWidget
from app.people.models import Student
from app.people.models.profiles import Faculty
from app.registry.models import Registration

# ? should I have a User Ressource class and extand the profile from it ?


class FacultyResource(resources.ModelResource):
    """
    Expected CSV columns
    ────────────────────
    faculty        ← long display name (“Dr. Jane A. Doe PhD”…)
    college_code   ← optional – defaults to “COAS”
    """

    staff_profile = fields.Field(
        column_name="faculty",
        attribute="staff_profile",
        widget=StaffProfileWidget(),
    )
    college = fields.Field(
        column_name="college_code", attribute="college", widget=CollegeWidget()
    )
    academic_rank = fields.Field(
        column_name="rank",
        attribute="academic_rank",
        default="Lecturer",
    )

    class Meta:
        model = Faculty
        import_id_fields = ("staff_profile",)
        fields = ("staff_profile", "college", "academic_rank")
        skip_unchanged = True
        report_skipped = False


class StudentResource(resources.ModelResource):
    """Resource for bulk importing :class:`Student` rows."""

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
