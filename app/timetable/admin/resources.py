from datetime import date
from pathlib import Path

from import_export import fields, resources

from app.academics.admin.widgets import CourseWidget
from app.academics.models import Course
from app.people.admin.widgets import FacultyProfileWidget
from app.people.models.profile import FacultyProfile
from app.spaces.admin.widgets import RoomWidget
from app.spaces.models.core import Room
from app.timetable.models import AcademicYear, Section, Semester
from app.timetable.models.schedule import Schedule

from .widgets import AcademicYearWidget, SectionWidget, SemesterCodeWidget


class ScheduleResource(resources.ModelResource):
    room = fields.Field(
        column_name="location",
        attribute="location",
        widget=RoomWidget(model=Room, field="location"),
    )
    faculty = fields.Field(
        column_name="faculty",
        attribute="faculty",
        widget=FacultyProfileWidget(model=FacultyProfile, field="full_name"),
    )
    section = fields.Field(
        column_name="section",
        attribute="section",
        widget=SectionWidget(model=Section, field="id"),
    )

    class Meta:
        model = Schedule
        import_id_fields = ("weekday", "location", "faculty", "start_time")


class SectionResource(resources.ModelResource):
    course = fields.Field(
        column_name="course_code",
        attribute="course",
        widget=CourseWidget(model=Course, field="id"),
    )
    semester = fields.Field(
        column_name="semester",
        attribute="semester",
        widget=SemesterCodeWidget(model=Semester, field="id"),
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
    number = fields.Field(
        column_name="semester",
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
            "short_name",
        )
