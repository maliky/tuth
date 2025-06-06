"""Widgets module."""

import re
from datetime import date
from typing import Tuple, cast

from import_export import widgets

from app.academics.admin.widgets import CourseCodeWidget
from app.academics.models import Course
from app.shared.enums import WEEKDAYS_NUMBER
from app.timetable.models import AcademicYear, Section, Semester


class WeekdayWidget(widgets.IntegerWidget):
    """Accept either the integer 1-7 or the English weekday name."""

    def clean(self, value, row=None, *args, **kwargs):
        _map = {label.lower(): num for num, label in WEEKDAYS_NUMBER.choices}

        if value is None or not value:
            return None

        token = str(value).strip().lower()
        if token.isdigit():
            return int(token)

        assert token in _map, f"{token} is not in {_map}"
        return _map[token]


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


class SemesterCodeWidget(widgets.ForeignKeyWidget):
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


class SectionCodeWidget(widgets.Widget):
    """Parse ``YY-YY_SemN:section`` strings and return Semester + number."""

    def __init__(self, semester_widget: SemesterCodeWidget | None = None) -> None:
        super().__init__()
        self.semester_widget = semester_widget or SemesterCodeWidget(
            model=Semester, field="id"
        )
        self.number: int | None = None

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        sem_token, num_token = value.split(":", 1)
        semester = self.semester_widget.clean(sem_token.strip(), row, *args, **kwargs)
        number = int(num_token.strip()) if num_token.strip().isdigit() else None
        self.number = number
        return semester, number


class SectionWidget(widgets.ForeignKeyWidget):
    """
    Parse four CSV columns (ay, sem#, course code, section#) and return a Section.
    Expected CSV headers:  academic_year, semester, course, section_no
    """

    ay_widget = AcademicYearWidget(model=AcademicYear, field="short_name")
    c_widget = CourseCodeWidget(model=Course, field="code")  # creates Course if needed

    def _parse_row(self, row) -> Tuple[AcademicYear, Semester, Course | None, int]:
        ay_token = (row.get("academic_year") or "").strip()
        sem_no_raw = (row.get("semester") or "").strip()
        course_raw = (row.get("course") or "").strip()
        sec_no_raw = (row.get("section_no") or "").strip()

        if not (ay_token and sem_no_raw and course_raw and sec_no_raw):
            raise ValueError("Missing AY / semester / course / section_no")

        ay = cast(AcademicYear, self.ay_widget.clean(ay_token, row))
        sem_no = int(sem_no_raw)
        semester, _ = Semester.objects.get_or_create(academic_year=ay, number=sem_no)

        course = self.c_widget.clean(course_raw, row)

        sec_no = int(sec_no_raw)
        return ay, semester, course, sec_no

    # ------------ widget API ------------
    def clean(self, value, row=None, *args, **kwargs) -> Section | None:
        """
        *value* is ignored (we rely entirely on the other columns).
        """
        if row is None:
            raise ValueError("Row context required")

        _, semester, course, sec_no = self._parse_row(row)

        section, _ = Section.objects.get_or_create(
            semester=semester,
            course=course,
            number=sec_no,
        )
        return section

    def render(self, value: Section, obj=None):  # optional – for exports
        if not value:
            return ""
        return f"{value.semester}:{value.course.code}:s{value.number}"
