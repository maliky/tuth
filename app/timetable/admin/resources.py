from datetime import date
from pathlib import Path

from import_export import fields, resources, widgets

from app.academics.admin.widgets import CollegeWidget, CourseWidget
from app.academics.models.college import College
from app.academics.models.course import Course
from app.timetable.models import AcademicYear, Schedule, Section, Semester

from .widgets import AcademicYearWidget, SemesterWidget


class SectionResource(resources.ModelResource):
    course = fields.Field(
        column_name="course",
        attribute="course",
        widget=CourseWidget(model=Course, field="code"),
    )
    semester = fields.Field(
        column_name="semester",
        attribute="semester",
        widget=SemesterWidget(model=Semester, field="id"),
    )
    schedule = fields.Field(
        column_name="schedule",
        attribute="schedule",
        widget=widgets.ForeignKeyWidget(Schedule, field="id"),
    )

    def save_instance(self, instance, is_create, row, **kwargs):
        """Wrap save to log errors during import."""
        try:
            return super().save_instance(instance, is_create, row, **kwargs)
        except Exception as exc:  # pragma: no cover - log & abort
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            logfile = log_dir / f"import_{date.today():%Y%m%d}.log"
            with logfile.open("a") as fh:
                fh.write(f"{exc}\n")
            raise

    class Meta:
        model = Section
        import_id_fields = ("number", "course", "semester")
        skip_unchanged = True


class SemesterResource(resources.ModelResource):
    academic_year = fields.Field(
        column_name="academic_year",
        attribute="academic_year",
        widget=AcademicYearWidget(model=AcademicYear, field="short_name"),
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
