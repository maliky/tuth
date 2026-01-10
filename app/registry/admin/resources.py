"""Resource module for the registry."""

from import_export import fields, resources

from app.people.admin.widgets import StudentGradeWidget, StudentUserWidget
from app.registry.admin.resources_mapping import GRADE_HEADER_MAP
from app.registry.admin.widgets import GradeValueWidget
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.registration import Registration
from app.shared.utils import get_in_row
from app.timetable.admin.resource_mapping import SECTION_HEADER_MAP
from app.timetable.admin.section_widgets import SectionWidget
from app.timetable.utils import normalize_academic_year


class GradeResource(resources.ModelResource):
    """Import grades from a flat csv file.

    Requires: student_id, grade_code, academic_year, semester_no,
    college_code, dept_no, course_no, credit_hours, section_no,curriculum.
    """

    # check the Widget
    student = fields.Field(
        column_name="student_id",
        attribute="student",
        widget=StudentUserWidget(),
    )
    section = fields.Field(
        column_name="section_no",
        attribute="section",
        widget=SectionWidget(fuzzy_threshold=1.0),
    )
    value = fields.Field(
        attribute="value", column_name="grade_code", widget=GradeValueWidget()
    )

    class Meta:
        model = Grade
        import_id_fields = ("student", "section", "grade_code")

    def before_import(self, dataset):
        """Normalize grade file headers."""
        headers = dataset.headers or []
        dataset.headers = [GRADE_HEADER_MAP.get(h, h) for h in headers]
        dataset.headers = [SECTION_HEADER_MAP.get(h, h) for h in headers]


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
