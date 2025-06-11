"""Import/export resources for timetable models. (Section)"""

from import_export import fields, resources

from app.academics.admin.widgets import CourseWidget
from app.people.admin.widgets import FacultyProfileWidget
from app.timetable.admin.widgets import SemesterWidget
from app.timetable.models.section import Section


class SectionResource(resources.ModelResource):
    academic_year = fields.Field(
        column_name="academic_year",
        attribute="semester",
        widget=SemesterWidget(),
    )
    semester = fields.Field(
        column_name="semester_no",
        attribute="semester",
        widget=SemesterWidget(),
    )
    course = fields.Field(
        # could be other course columns
        column_name="course_name",
        attribute="course",
        widget=CourseWidget(),
    )
    number = fields.Field(column_name="section_no", attribute="number")
    faculty = fields.Field(
        column_name="faculty",
        attribute="faculty",
        widget=FacultyProfileWidget(),
    )

    # def save_instance(
    #     self,
    #     instance: Section,
    #     is_create: bool,
    #     row: dict[str, str],
    #     **kwargs,
    # ):
    #     """Wrap save to log errors during import."""
    #     try:
    #         return super().save_instance(instance, is_create, row, **kwargs)
    #     except Exception as exc:  # pragma: no cover - log & abort
    #         log_dir = Path("logs")
    #         log_dir.mkdir(exist_ok=True)
    #         logfile = log_dir / f"import_{date.today():%Y%m%d}.log"
    #         with logfile.open("a") as fh:
    #             fh.write(f"{exc}\n")
    #         raise

    class Meta:
        model = Section
        import_id_fields = ("number", "course", "semester", "faculty", "academic_year")
        fields = ("number", "course", "semester", "faculty", "academic_year")
        skip_unchanged = True
        use_bulk = False
