"""Timetable.admin.widgets.section module."""

from typing import Optional, cast

from import_export import widgets

from app.academics.admin.widgets import (
    CourseWidget,
    CurriculumCourseWidget,
    CurriculumWidget,
)
from app.people.admin.widgets import FacultyWidget
from app.timetable.ensures import ensure_semester, ensure_section
from app.shared.utils import get_in_row
from app.timetable.admin.widgets.core import SemesterCodeWidget, SemesterWidget
from app.timetable.models.section import Section


class SectionWidget(widgets.ForeignKeyWidget):
    """Create a Section from multiple CSV columns."""

    def __init__(self, *, fuzzy_threshold: float = 1.0):
        super().__init__(Section)  # using pk until export is done
        self.curriculum_course_w = CurriculumCourseWidget()
        self.sem_w = SemesterWidget()
        self.faculty_w = FacultyWidget()
        self.fuzzy_threshold = fuzzy_threshold
        self._cache: dict[tuple[int, int, int, int | None], Section] = {}

    # ------------ widget API ------------
    def clean(self, value, row=None, *args, **kwargs) -> Section | None:
        """Return the Section referenced by the CSV row."""
        if row is None:
            raise ValueError("Row context required")

        # needs course in context
        curriculum_value = get_in_row("curriculum", row)
        curriculum_course = self.curriculum_course_w.clean(
            value=curriculum_value, row=row
        )

        semester_no = get_in_row("semester_no", row)
        academic_year = get_in_row("academic_year", row)
        semester = ensure_semester(academic_year, semester_no)

        faculty_value = get_in_row("faculty", row)
        faculty = self.faculty_w.clean(value=faculty_value, row=row)

        sec_no_value = value or "0"

        if sec_no_value.isdigit():
            number = int(sec_no_value)
        else:
            number = 0

        key = (
            semester.id if semester else 0,
            curriculum_course.id if curriculum_course else 0,
            number,
            faculty.id if faculty else None,
        )
        cached = self._cache.get(key)
        if cached:
            return cached

        section = ensure_section(
            semester=semester,
            curriculum_course=curriculum_course,
            number=number,
            faculty_id=faculty.id if faculty else None,
        )
        self._cache[key] = section

        return cast(Optional[Section], section)

    def render(self, value: Section, obj=None):
        """Render the values for exports."""
        if not value:
            return ""
        return f"{value.semester}:{value.course.code}:s{value.number}"


class SectionCodeWidget(widgets.Widget):
    """Resolve YY-YY_SemN:sec_no codes into :class:Section objects."""

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
        """Return the Section identified by the import code string."""
        course_dept_value = row.get("course_dept", "").strip()
        course = self.crs_w.clean(value=course_dept_value, row=row)

        sem_code_value, _, sec_no = [v.strip() for v in value.partition(":")]

        semester = self.sem_w.clean(value=sem_code_value, row=row)
        number = int(sec_no) if sec_no.isdigit() else None

        section, _ = Section.objects.get_or_create(
            semester=semester, course=course, number=number
        )

        return section
