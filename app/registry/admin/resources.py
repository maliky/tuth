"""Resource module for the registry."""

from import_export import fields, resources

from app.people.admin.widgets import GradeStudentWidget
from app.registry.admin.widgets import GradeValueWidget
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.registration import Registration
from app.timetable.admin.widgets.section import SectionWidget


def _normalize_year_code(raw: str | None) -> str:
    """Return a YY-YY code from YYYY/YYYY or YYYY strings."""
    text = (raw or "").strip().replace(" ", "").replace("/", "-")
    if not text:
        return ""
    if len(text) == 9 and text[4] == "-":
        return f"{text[2:4]}-{text[7:9]}"
    if len(text) == 4 and text.isdigit():
        yy = text[2:4]
        return f"{yy}-{int(yy) + 1:02d}"
    return text


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

    def before_import_row(self, row, **kwargs):
        """Normalize academic year and semester tokens before widgets run."""
        academic_year = row.get("academic_year")
        if academic_year:
            row["academic_year"] = _normalize_year_code(academic_year)
        semester_value = row.get("semester_no").strip()
        if semester_value not in (None, ""):
            row["semester_no"] = str(semester_value)
        return super().before_import_row(row, **kwargs)


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
