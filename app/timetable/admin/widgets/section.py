"""timetable.admin.widgets.section module"""

from typing import Optional, cast
from import_export import widgets

from app.academics.admin.widgets import CourseWidget
from app.timetable.admin.widgets.core import SemesterWidget
from app.timetable.models.section import Section


class SectionWidget(widgets.ForeignKeyWidget):
    "Parse the necessary CSV columns (no, section code) to get a section object."

    def __init__(self):
        super().__init__(Section)  # using pk until export is done
        self.course_w = CourseWidget()
        self.sem_w = SemesterWidget()

    # ------------ widget API ------------
    def clean(self, value, row=None, *args, **kwargs) -> Section | None:
        """
        *value* is ignored (we rely entirely on the other columns).
        """
        if row is None:
            raise ValueError("Row context required")

        sem_no_value, course_name_value, sec_no_value = [
            row.get(v, "").strip() for v in ("semester_no", "course_name", "section_no")
        ]

        semester = self.sem_w.clean(value=sem_no_value, row=row)
        course = self.course_w.clean(value=course_name_value, row=row)

        number = int(sec_no_value)

        section, _ = Section.objects.get_or_create(
            semester=semester, course=course, number=number
        )
        return cast(Optional[Section], section)

    def render(self, value: Section, obj=None):  # optional – for exports
        if not value:
            return ""
        return f"{value.semester}:{value.course.code}:s{value.number}"


class SectionCodeWidget(widgets.Widget):
    """Parse ``YY-YY_SemN:sec_no`` strings and a section"""

    def __init__(self) -> None:
        super().__init__(Section)
        self.sem_w = SemesterWidget()
        self.crs_w = CourseWidget()

    def clean(
        self,
        value: str,
        row: dict[str, str],
        *args,
        **kwargs,
    ) -> Section | None:
        "Expecting the value to be"

        course_name_value = row.get("course_name", "").strip()
        course = self.crs_w.clean(value=course_name_value, row=row)

        sem_code_value, _, sec_no = [v.strip() for v in value.partition(":")]

        semester = self.sem_w.clean(value=sem_code_value, row=row)
        number = int(sec_no) if sec_no.isdigit() else None

        section, _ = Section.objects.get_or_create(
            semester=semester, course=course, number=number
        )

        return section
