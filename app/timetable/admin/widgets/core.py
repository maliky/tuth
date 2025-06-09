"""timetable.admin.widgets.core module."""

import re
from datetime import date

from import_export import widgets

from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester


class AcademicYearCodeWidget(widgets.ForeignKeyWidget):
    """Create an academic year from its code. eg 25-26"""

    def __init__(self, *args, **kwargs):
        super().__init__(AcademicYear, field="code")
        self.ay_pat = re.compile(r"^(\d{2})-(\d{2})$")

    def clean(self, value, row=None, *args, **kwargs):

        if not value:
            return None

        m = self.ay_pat.match(value)

        assert m, f"Invalid academic year short name, but got {m} for {self.ay_pat}"

        start_year = int("20" + m.group(1))
        ay, _ = AcademicYear.objects.get_or_create(
            code=value,
            defaults={"start_date": date(start_year, 8, 11)},
        )
        return ay

    def before_import_row(self, row, **kwargs):
        # auto-create AY if missing
        short = row["academic_year"]
        if not AcademicYear.objects.filter(code=short).exists():
            ys, ye = short.split("-")  # '25-26' -> '25', '26'
            AcademicYear.objects.create(
                start_date=date(int("20" + ys), 9, 1),
                # end_date=date(int("20" + ye), 8, 31),
            )


class SemesterWidget(widgets.ForeignKeyWidget):
    """Derive the Semester from a semestr no and an academic year code"""

    def __init__(self):
        super().__init__(Semester)  # using pk until start_date can be proven to be uniq
        self.ay_w = AcademicYearCodeWidget()

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None

        sem_no = value.strip()

        assert "academic_year" in row, f"not `academic_year` found in {row}"
        ay_code_value = row.get("academic_year", "").strip()

        ay = self.ay_w.clean(value=ay_code_value, row=row)

        semester, _ = Semester.objects.get_or_create(
            academic_year=ay,
            number=sem_no,
        )

        return semester


class SemesterCodeWidget(widgets.ForeignKeyWidget):
    """Parse ``YY-YY_SemN`` notation and return the :class:`Semester`."""

    def __init__(self):
        super().__init__(Semester)
        self.sem_pat = re.compile(r"^(?P<year>\d{2}-\d{2})_Sem(?P<num>\d+)$")

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None

        m = self.sem_pat.match(value)

        assert m, f"Invalid semester format, got {m} for {self.sem_pat}"

        ay_short = m.group("year")
        sem_no = int(m.group("num"))
        start_year = int("20" + ay_short.split("-")[0])
        ay, _ = AcademicYear.objects.get_or_create(
            code=ay_short,
            defaults={"start_date": date(start_year, 8, 11)},
        )
        semester, _ = Semester.objects.get_or_create(
            academic_year=ay,
            number=sem_no,
        )
        return semester
