"""Resource module for the registry."""

from import_export import fields, resources

from app.people.admin.widgets import GradeStudentWidget
from app.registry.admin.widgets import GradeValueWidget
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.registration import Registration
from app.shared.utils import get_in_row
from app.timetable.admin.widgets.section import SectionWidget
from app.timetable.utils import normalize_academic_year


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
        attribute="section",
        column_name="section_no",
        widget=SectionWidget(fuzzy_threshold=1.0),
    )
    value = fields.Field(
        attribute="value", column_name="grade_code", widget=GradeValueWidget()
    )

    class Meta:
        model = Grade
        import_id_fields = ("student", "section")

    def before_import_row(self, row, **kwargs):
        """Normalize academic year and semester tokens before widgets run."""
        # The idea here is to normalize the columns. This should be done in
        # a more generic way.
        academic_year = get_in_row("AcademicYear", row)
        if academic_year:
            row["academic_year"] = normalize_academic_year(academic_year)
        semester_value = get_in_row("Semester", row)
        if semester_value:
            row["semester_no"] = semester_value
        return super().before_import_row(row, **kwargs)

    def handle_integrity_error(self, instance, error, row=None, import_result=None, **kwargs):
        """Log integrity errors (duplicates) and continue batch processing."""
        if import_result is not None and row is not None:
            import_result.add_error(row, error)
        return None


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
