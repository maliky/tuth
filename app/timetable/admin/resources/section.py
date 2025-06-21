"""Import/export resources for section models."""

from typing import Any

from import_export import fields, resources

from app.academics.admin.widgets import ProgramWidget
from app.people.admin.widgets import FacultyWidget
from app.timetable.admin.widgets.core import SemesterWidget
from app.timetable.models.section import Section


class SectionResource(resources.ModelResource):

    # just to keep it in headers and accessible for other.
    academic_year = fields.Field(attribute=None, column_name="academic_year")
    course_no = fields.Field(attribute=None, column_name="course_no")
    course_dept = fields.Field(attribute=None, column_name="course_dept")
    college_code = fields.Field(attribute=None, column_name="college_code")

    # for this section, it is mandatory that the semester be attached to a year
    # when exporting we should export the semester_code
    semester = fields.Field(
        attribute="semester",
        column_name="semester_no",
        widget=SemesterWidget(),
    )
    program = fields.Field(
        # could be other course columns
        attribute="program",
        column_name="curriculum",
        widget=ProgramWidget(),
    )
    number = fields.Field(attribute="number", column_name="section_no")

    faculty = fields.Field(
        column_name="faculty",
        attribute="faculty",
        widget=FacultyWidget(),
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def before_import(self, dataset, **kwargs):
        """Is this realy usefull ?"""
        super().before_import(dataset, **kwargs)

    class Meta:
        model = Section
        import_id_fields = ("semester", "program", "number", "faculty")
        fields = (
            "number",
            "program",
            "semester",
            "faculty",
            "course_dept",
            "academic_year",
            "course_no",
            "college_code",
        )
        skip_unchanged = True
        use_bulk = False
