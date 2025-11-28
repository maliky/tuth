"""Resource module for the registry."""

from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from app.people.admin.widgets import StudentUserWidget
from app.people.models.student import Student
from app.registry.models.grade import Grade
from app.registry.models.registration import Registration
from app.timetable.admin.widgets.section import SectionWidget
from app.timetable.admin.widgets.session import SecSessionWidget


class GradeResource(resources.ModelResource):
    """Import grades from a flat csv file.

    Requires: student_id, grade_code, academic_year, semester_no,
    college_code, dept_no, course_no, credit_hours, section_no,curriculum.
    """

    # check the Widget
    student = fields.Field(
        attribute="student",
        column_name="student_id",
        widget=ForeignKeyWidget(Student, field="StudentID"),
    )
    section = fields.Field(
        attribute="section", column_name="section_no", widget=SectionWidget()
    )
    value = fields.Field(attribute="value", column_name="grade_code")

    class Meta:
        model = Grade
        import_id_fields = (
            "student_id",
            "grade_code",
            "academic_year",
            "semester_no",
            "dept_no",
            "course_no",
            "credit_hours",
            "section_no",
            "curriculum",
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
