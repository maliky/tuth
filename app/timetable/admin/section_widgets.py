"""Timetable.admin.widgets.section module."""

from typing import Optional, cast

from import_export import widgets

from app.academics.admin.widgets import (
    CourseWgt,
    CurriCourseWgt,
    CurriWgt,
)
from app.people.admin.widgets import FacultyFullnameWgt
from app.timetable.ensures import ensure_sem, ensure_sec, ensure_sem_code
from app.shared.utils import get_in_row, asserts_keys, to_int
from app.timetable.admin.core_widgets import SemCodeWgt, SemWgt
from app.timetable.utils import parse_sem_code
from app.timetable.models.section import Section


class SecWgt(widgets.ForeignKeyWidget):
    """Create a Section from multiple CSV columns."""

    def __init__(self, *, fuzzy_threshold: float = 1.0):
        super().__init__(Section)  # using pk until export is done
        self.curriculum_course_w = CurriCourseWgt()
        self.sem_w = SemWgt()
        self.faculty_w = FacultyFullnameWgt()
        self.fuzzy_threshold = fuzzy_threshold
        self._cache: dict[tuple[int, int, int, int | None], Section] = {}

    # ------------ widget API ------------
    def clean(self, value, row=None, *args, **kwargs) -> Section | None:
        """Return the Section referenced by the sec_no as value."""

        sec_value = (value or "0").strip()
        if not sec_value:
            return None
        sec_no = to_int(sec_value)

        asserts_keys(
            ["curriculum", "course_no", "dept_code", "college_code", "faculty"], row
        )

        curriculum_value = get_in_row("curriculum", row)
        curriculum_course = self.curriculum_course_w.clean(curriculum_value, row=row)

        #  if we do not have semester_no or academic_year, we default to 25-26s2 sem.
        semester_value = get_in_row("semester_no", row)
        academic_value = get_in_row("academic_year", row)
        semester = ensure_sem(academic_value, semester_value, default="25-26s2")

        faculty_value = get_in_row("faculty", row)
        faculty = self.faculty_w.clean(faculty_value, row=row)

        key = (
            semester.id,
            curriculum_course.id,
            sec_no,
            faculty.id if faculty else None,
        )
        cached = self._cache.get(key)
        if cached:
            return cached

        section = ensure_sec(
            semester=semester,
            curriculum_course=curriculum_course,
            number=sec_no,
            faculty_id=faculty.id if faculty else None,
        )
        self._cache[key] = section

        return cast(Optional[Section], section)

    def render(self, value: Section, obj=None):
        """Render the values for exports."""
        if not value:
            return ""
        return f"{value.semester}:{value.course.code}:s{value.number}"


class SecCodeWgt(widgets.Widget):
    """Resolve YY-YY_SemN:sec_no codes into :class:Section objects."""

    def __init__(self) -> None:
        super().__init__(Section)
        self.crs_w = CourseWgt()

    def clean(
        self,
        value: str,
        row: dict[str, str],
        *args,
        **kwargs,
    ) -> Section | None:
        """Return the Section identified by the import code string."""

        course_dept_value = get_in_row("course_dept", row)
        course = self.crs_w.clean(value=course_dept_value, row=row)

        sem_code_value, _, sec_value = [v.strip() for v in value.partition(":")]

        ay_code, sem_no = parse_sem_code(sem_code_value)
        if not ay_code and not sem_no:
            return None

        section, _ = Section.objects.get_or_create(
            semester=ensure_sem_code(sem_code_value),
            course=course,
            number=to_int(sec_value),
        )

        return section
