from import_export import fields, resources

from app.timetable.admin.widgets.core import AcademicYearCodeWidget
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester


class SemesterResource(resources.ModelResource):
    academic_year = fields.Field(
        column_name="academic_year",
        attribute="academic_year",
        widget=AcademicYearCodeWidget(),
    )
    number = fields.Field(
        column_name="semester_no",
        attribute="number",
    )

    class Meta:
        model = Semester
        import_id_fields = ("academic_year", "number")
        fields = (
            "academic_year",
            "number",
            "start_date",
            "end_date",
        )  # do not remove academic_year


class AcademicYearResource(resources.ModelResource):
    class Meta:
        model = AcademicYear
        import_id_fields = ("start_date",)
        fields = (
            "start_date",
            "end_date",
            "long_name",
            "code",
        )
