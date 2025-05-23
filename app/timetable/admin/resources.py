from datetime import date
from pathlib import Path
from import_export import fields, resources
from app.academics.models.college import College
from app.academics.models.course import Course
from app.timetable.models import AcademicYear, Section, Semester

from .widgets import AcademicYearWidget, CollegeWidget, CourseWidget, SemesterWidget


class SectionResource(resources.ModelResource):
    college = fields.Field(
        column_name="college",
        widget=CollegeWidget(College, "code"),
        # readonly=True,
    )
    course = fields.Field(
        column_name="course",
        attribute="course",
        widget=CourseWidget(Course, "code"),
    )
    semester = fields.Field(
        column_name="semester",
        attribute="semester",
        widget=SemesterWidget(Semester, "id"),
    )

    def save_instance(self, instance, using_transactions=True, dry_run=False):
        try:
            return super().save_instance(instance, using_transactions, dry_run)
        except Exception as exc:  # pragma: no cover - log & abort
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            logfile = log_dir / f"import_{date.today():%Y%m%d}.log"
            with logfile.open("a") as fh:
                fh.write(f"{exc}\n")
            raise

    class Meta:
        model = Section
        import_id_fields = ("course", "semester", "number")
        skip_unchanged = True


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


class AcademicYearResource(resources.ModelResource):
    class Meta:
        model = AcademicYear
        import_id_fields = ("start_date",)
        fields = (
            "start_date",
            "end_date",
            "long_name",
            "short_name",
        )
