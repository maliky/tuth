from datetime import date
from pathlib import Path
from import_export import fields, resources
from app.timetable.models import AcademicYear, Section, Semester

from .widgets import AcademicYearWidget


class SectionResource(resources.ModelResource):
    def before_import_row(self, row, **kwargs):
        """Create missing academic years or semesters on the fly."""
        ay_short = row.get("academic_year")
        sem_no = row.get("semester")
        if ay_short:
            ay, _ = AcademicYear.objects.get_or_create(
                short_name=ay_short,
                defaults={"start_date": date(int("20" + ay_short.split("-")[0]), 9, 1)},
            )
            if sem_no:
                Semester.objects.get_or_create(
                    academic_year=ay,
                    number=int(sem_no),
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
