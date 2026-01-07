"""timetable.admin.widgets.core module."""

import re
from datetime import date

from import_export import widgets

from app.shared.utils import get_in_row
from app.timetable.ensures import ensure_semester
from app.timetable.models.academic_year import AcademicYear
from app.timetable.models.semester import Semester
from app.timetable.utils import parse_semester_code


def ensure_academic_year_code(code: str | None) -> AcademicYear:
    """Look up or auto-create an AcademicYear from its 'YY-YY' code.

    If no code return current AcademicYear, the code should be properly formated.
    """
    code = (code or "").strip()
    if not code:
        return AcademicYear.get_default()

    ys, _ = code.split("-")
    start = date(int("20" + ys), 9, 1)

    ay_obj, _created = AcademicYear.objects.get_or_create(
        code=code, defaults={"start_date": start}
    )

    if _created:  # > is this really necessary ?
        ay_obj.save()

    return ay_obj


class AcademicYearCodeWidget(widgets.ForeignKeyWidget):
    """Convert YY-YY codes into :class:AcademicYear objects."""

    def __init__(self, *args, **kwargs):
        super().__init__(AcademicYear, field="code")
        self.ay_pat = re.compile(r"^(\d{2})(?:[-/])(?:20)?(\d{2})$")

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
        if not m:
            raise ValueError(
                f"Invalid academic year short name, got '{value!r}';" f"for {self.ay_pat}"
            )

        start = date(int("20" + m.group(1)))
        ay, ay_created = AcademicYear.objects.get_or_create(
            code=value, defaults={"start_date": start}
        )

        if ay_created:
            ay.save()

        return ay


class SemesterWidget(widgets.ForeignKeyWidget):
    """Build a Semester from its number and academic year."""

    def __init__(self):
        # using pk until start_date can be proven to be uniq
        super().__init__(Semester)
        self.ay_w = AcademicYearCodeWidget()

    def clean(
        self,
        value: str | None,
        row: dict[str, str],
        *args,
        **kwargs,
    ) -> Semester | None:
        """Get the semester from a number and look-up for the academic year code."""
        # may be good to use ensure_semester with a default
        if not value:
            return None

        sem_no = value.strip()
        ay_code_value = get_in_row("academic_year", row)

        ay = self.ay_w.clean(value=ay_code_value, row=row)

        semester, semester_created = Semester.objects.get_or_create(
            academic_year=ay, number=sem_no
        )
        # if semester_created:  # not sure if this is necessary.
        #     semester.save()
        return semester


class SemesterCodeWidget(widgets.ForeignKeyWidget):
    """Parse YY-YY_SemN like strings into :class:Semester objects."""

    def __init__(self, pat: str | None = None):
        super().__init__(Semester)

    def clean(
        self,
        value: str | None,
        row: dict[str, str] | None = None,
        *args,
        **kwargs,
    ) -> Semester | None:
        """Get the semester and the ay directly from '24-25_Sem2' or '24-25s2' code."""

        if not value:
            return None

        ay_code, sem_code = parse_semester_code(value)
        sem_obj = ensure_semester(ay_code, sem_code)

        return sem_obj
