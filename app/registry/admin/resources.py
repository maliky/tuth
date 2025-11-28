from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from app.people.admin.widgets import StudentUserWidget
from app.timetable.admin.widgets.section import SectionShortCodeWidget


class GradeResource(resources.ModelResource):
    """
    Import grades from a flat csv file:
    'student_id, curriculum_short_code, section_short_code, grade_code'
    """

    # check the Widget
    student_id = fields.Field(
        attribute="student",
        column_name="student_id",
        widget=ForeignKeyWidget(Student, field="student_id"),
    )
    section_short_code = fiels.Field(
        attribute="section",
        column_name="section_short_code",
        widgets=SectionShortCodeWidget(),
    )
    grade_code = fields.Field(
        attribute="value", column_name="grade_code", widget=GradeValueCodeWdiget()
    )

    class Meta:
        model = Grade
        import_id_fields = ("student_id", "curriculum_short_code", "section_short_code")


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
