"""Resource module for the registry."""

from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from app.people.admin.widgets import GradeStudentWidget
from app.people.models.student import Student
from app.registry.admin.widgets import GradeValueWidget
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.registration import Registration
from app.timetable.admin.widgets.section import SectionWidget


class GradeResource(resources.ModelResource):
    """Import grades from a flat csv file.

    Requires: student_id, grade_code, academic_year, semester_no,
    college_code, dept_no, course_no, credit_hours, section_no,curriculum.
    """

    # check the Widget
    student = fields.Field(
        attribute="student",
        column_name="student_id",
        widget=GradeStudentWidget(),
    )
    section = fields.Field(
        attribute="section", column_name="section_no", widget=SectionWidget()
    )
    value = fields.Field(
        attribute="value", column_name="grade_code", widget=GradeValueWidget()
    )

    class Meta:
        model = Grade
        import_id_fields = ("student", "section")


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
