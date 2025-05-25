from import_export import widgets
from app.timetable.models import AcademicYear, Semester
import re
from datetime import date


class AcademicYearWidget(widgets.ForeignKeyWidget):
    """Create an academic year from a short name if needed."""

    pattern = re.compile(r"^(\d{2})-(\d{2})$")

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        match = self.pattern.match(value)
        if not match:
            raise ValueError("Invalid academic year short name")
        start_year = int("20" + match.group(1))
        ay, _ = AcademicYear.objects.get_or_create(
            short_name=value,
            defaults={"start_date": date(start_year, 8, 11)},
        )
        return ay

    def before_import_row(self, row, **kwargs):
        # auto-create AY if missing
        short = row["academic_year"]
        if not AcademicYear.objects.filter(short_name=short).exists():
            ys, ye = short.split("-")  # '25-26' -> '25', '26'
            AcademicYear.objects.create(
                start_date=date(int("20" + ys), 9, 1),
                #                end_date=date(int("20" + ye), 8, 31),
            )

    class Meta:
        model = Semester
        import_id_fields = ("academic_year", "number")
        fields = ("academic_year", "number", "start_date", "end_date")


class SemesterWidget(widgets.ForeignKeyWidget):
    """Parse ``YY-YY_SemN`` notation and return the :class:`Semester`."""

    pattern = re.compile(r"^(?P<year>\d{2}-\d{2})_Sem(?P<num>\d+)$")

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        match = self.pattern.match(value)
        if not match:
            raise ValueError("Invalid semester format")
        ay_short = match.group("year")
        sem_no = int(match.group("num"))
        start_year = int("20" + ay_short.split("-")[0])
        ay, _ = AcademicYear.objects.get_or_create(
            short_name=ay_short,
            defaults={"start_date": date(start_year, 8, 11)},
        )
        semester, _ = Semester.objects.get_or_create(
            academic_year=ay,
            number=sem_no,
        )
        return semester
