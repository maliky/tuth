from import_export import fields, resources
from app.timetable.models import Section, Semester

from .widgets import AcademicYearWidget


class SectionResource(resources.ModelResource):
    class Meta:
        model = Section
        import_id_fields = ("course", "semester", "number")


class SemesterResource(resources.ModelResource):
    academic_year = fields.Field(
        column_name="academic_year",
        attribute="academic_year",
        widget=AcademicYearWidget("academic_year", "short_name"),
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
