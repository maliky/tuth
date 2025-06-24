"""timetable.admin.widgets.core module."""

import re
from datetime import date

from import_export import widgets

from app.shared.utils import CachedWidgetMixin

from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester


def ensure_academic_year_code(code: str) -> AcademicYear:
    """Look up or auto-create an AcademicYear from its 'YY-YY' code."""
    code = code.strip()
    if not AcademicYear.objects.filter(code=code).exists():
        ys, _ = code.split("-")
        start = date(int("20" + ys), 9, 1)
        AcademicYear.objects.create(start_date=start, code=code)

    return AcademicYear.objects.get(code=code)


class AcademicYearCodeWidget(CachedWidgetMixin, widgets.ForeignKeyWidget):
    """Convert YY-YY codes into :class:AcademicYear objects."""

    def __init__(self, *args, **kwargs):
        super().__init__(AcademicYear, field="code")
        self.ay_pat = re.compile(r"^(\d{2})-(\d{2})$")

    def clean(
        self,
        value: str | None,
        row: dict[str, str] | None = None,
        *args,
        **kwargs,
    ) -> AcademicYear | None:
        """Get the academic year from the code YY-YY."""
        if not value:
            return None

        m = self.ay_pat.match(value)

        assert m, f"Invalid academic year short name, but got {m} for {self.ay_pat}"

        key = value
        if key in self._cache:
            return self._cache[key]

        start_year = int("20" + m.group(1))
        ay, ay_created = AcademicYear.objects.get_or_create(
            code=value,
            defaults={"start_date": date(start_year, 8, 11)},
        )
        if ay_created:
            ay.save()

        self._cache[key] = ay

        return ay

    def after_import(self, dataset, result, **kwargs):
        super().after_import(dataset, result, **kwargs)


class SemesterWidget(CachedWidgetMixin, widgets.ForeignKeyWidget):
    """Build a :class:Semester from its number and academic year."""

    def __init__(self):
        super().__init__(Semester)  # using pk until start_date can be proven to be uniq
        self.ay_w = AcademicYearCodeWidget()

    def clean(
        self,
        value: str | None,
        row: dict[str, str],
        *args,
        **kwargs,
    ) -> Semester | None:
        """Get the semester from a number and look for the academic year code also."""
        if not value:
            return None

        sem_no = value.strip()
        ay_code_value = row.get("academic_year", "").strip()

        ay = self.ay_w.clean(value=ay_code_value, row=row)

        key = (getattr(ay, "pk", None), sem_no)
        if key in self._cache:
            return self._cache[key]

        semester, semester_created = Semester.objects.get_or_create(
            academic_year=ay,
            number=sem_no,
        )
        if semester_created:
            semester.save()

        self._cache[key] = semester
        return semester

    def after_import(self, dataset, result, **kwargs):
        super().after_import(dataset, result, **kwargs)
        self.ay_w.after_import(dataset, result, **kwargs)


class SemesterCodeWidget(CachedWidgetMixin, widgets.ForeignKeyWidget):
    """Parse YY-YY_SemN strings into :class:Semester objects."""

    def __init__(self):
        super().__init__(Semester)
        self.sem_pat = re.compile(r"^(?P<year>\d{2}-\d{2})_Sem(?P<num>\d+)$")

    def clean(
        self,
        value: str | None,
        row: dict[str, str] | None = None,
        *args,
        **kwargs,
    ) -> Semester | None:
        """Get the semester and the ay directly from the fullfledge code."""
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

        key = (ay.pk, sem_no)
        if key in self._cache:
            return self._cache[key]

        semester, _ = Semester.objects.get_or_create(
            academic_year=ay,
            number=sem_no,
        )
        self._cache[key] = semester
        return semester

    def after_import(self, dataset, result, **kwargs):
        super().after_import(dataset, result, **kwargs)
