"""timetable.admin.widgets.section module."""

from typing import Optional, cast

from import_export import widgets

from app.shared.utils import CachedWidgetMixin

from app.academics.admin.widgets import CourseWidget, ProgramWidget
from app.people.admin.widgets import FacultyWidget
from app.timetable.admin.widgets.core import SemesterWidget
from app.timetable.models.section import Section


class SectionWidget(CachedWidgetMixin, widgets.ForeignKeyWidget):
    """Create a Section from multiple CSV columns."""

    def __init__(self):
        super().__init__(Section)  # using pk until export is done
        self.program_w = ProgramWidget()
        self.sem_w = SemesterWidget()
        self.faculty_w = FacultyWidget()

    # ------------ widget API ------------
    def clean(self, value, row=None, *args, **kwargs) -> Section | None:
        """Return the Section referenced by the CSV row."""
        if row is None:
            raise ValueError("Row context required")

        curriculum_value = (row.get("curriculum") or "").strip()
        program = self.program_w.clean(value=curriculum_value, row=row)

        semester_no = (row.get("semester_no") or "").strip()
        semester = self.sem_w.clean(value=semester_no, row=row)

        faculty_value = (row.get("faculty") or "").strip()
        faculty = self.faculty_w.clean(value=faculty_value, row=row)

        sec_no_value = (row.get("section_no") or "0").strip()

        if sec_no_value.isdigit():
            number = int(sec_no_value)
        else:
            number = 0

        key = (
            getattr(semester, "pk", None),
            getattr(program, "pk", None),
            number,
            getattr(faculty, "pk", None),
        )
        if key in self._cache:
            return cast(Optional[Section], self._cache[key])

        section, _ = Section.objects.get_or_create(
            semester=semester, program=program, number=number, faculty=faculty
        )
        self._cache[key] = section
        return cast(Optional[Section], section)

    def after_import(self, dataset, result, **kwargs):
        super().after_import(dataset, result, **kwargs)
        self.program_w.after_import(dataset, result, **kwargs)
        self.sem_w.after_import(dataset, result, **kwargs)
        self.faculty_w.after_import(dataset, result, **kwargs)

    def render(self, value: Section, obj=None):
        """Render the values for exports."""
        if not value:
            return ""
        return f"{value.semester}:{value.course.code}:s{value.number}"


class SectionCodeWidget(CachedWidgetMixin, widgets.Widget):
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

        key = (
            getattr(semester, "pk", None),
            getattr(course, "pk", None),
            number,
        )
        if key in self._cache:
            return self._cache[key]

        section, _ = Section.objects.get_or_create(
            semester=semester, course=course, number=number
        )

        self._cache[key] = section

        return section

    def after_import(self, dataset, result, **kwargs):
        super().after_import(dataset, result, **kwargs)
        self.sem_w.after_import(dataset, result, **kwargs)
        self.crs_w.after_import(dataset, result, **kwargs)
