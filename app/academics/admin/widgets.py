"""Widgets module."""

from typing import Any, Optional, cast

from import_export import widgets

from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.academics.models.program import Program
from app.shared.utils import expand_course_code


class ProgramWidget(widgets.ForeignKeyWidget):
    """Create or fetch Program rows from CSV data.

    The widget delegates curriculum and course parsing to CurriculumWidget
    and CourseWidget then assembles a :class:Program instance from
    the results.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(Program)
        self.curriculm_w = CurriculumWidget()
        self.course_w = CourseWidget()

    def clean(self, value, row=None, *args, **kwargs) -> Program | None:
        """Assemble course_dept, curriculum and course to return a curriculum course."""
        if not value:
            return None

        curriculum = cast(
            Curriculum, self.curriculm_w.clean(value=value.strip(), row=row)
        )

        course_dept_value = row.get("course_dept", "").strip()
        course = self.course_w.clean(value=course_dept_value, row=row)

        program, _ = Program.objects.get_or_create(
            curriculum=curriculum,
            course=course,
            credit_hours=row.get("credit_hours", "").strip(),
            is_required=row.get("is_required", True).strip(),
        )
        return program


class CurriculumWidget(widgets.ForeignKeyWidget):
    """Look up or create a :class:Curriculum from a short name.

    The associated college is determined from row['college_code'] when
    present. Missing curricula are created automatically.
    """

    def __init__(self):
        super().__init__(Curriculum, field="short_name")

    def clean(self, value, row=None, *args, **kwargs) -> Curriculum | None:
        """Returns a Curriculum object matching the provided short_name in value.

        Example input row:
          - row["curriculum"] = "Bsc Agriculture"
          - row["college_code"] = "CAFS" (optional, defaults to "COAS")

        Automatically creates curriculum with today's date.
        """
        if not value:
            return None

        college, _ = College.objects.get_or_create(
            code=row.get("college_code", "").strip()
        )

        curriculum, _ = Curriculum.objects.get_or_create(
            short_name=value.strip(),
            defaults={
                "short_name": value.strip(),
                "college": college,
            },
        )

        return curriculum


class CourseWidget(widgets.ForeignKeyWidget):
    """Convert course_* CSV columns into a :class:Course.

    course_dept and course_no identify the course while college is
    optional and defaults to "COAS". Results are cached to avoid duplicate
    queries when several rows reference the same course.
    """

    def __init__(self):
        super().__init__(Course, field="code")
        self.department_w = DepartmentWidget()
        self.college_w = CollegeWidget()
        self._cache = {}

    def clean(
        self,
        value: Any,
        row: Optional[dict[str, Any]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Course | None:
        """Return a Course gotten from dept, no and college_code.

        Value is ignored (import-export still passes the column declared in
        the resource, but the info we need is spread across *row*).
        """
        if row is None:
            return None
        course_dept = (row.get("course_dept") or "").strip().upper()
        department = self.department_w.clean(course_dept, row)

        course_no = row.get("course_no", "").strip()

        if not course_dept or not course_no:
            return None

        key = (department, course_no)
        if key in self._cache:
            return self._cache.get(key)

        course, _ = Course.objects.get_or_create(
            number=course_no,
            department=department,
        )
        self._cache[key] = course
        return course


class CourseManyWidget(widgets.ManyToManyWidget):
    """Parse list_courses and return a list of Course objects.

    The widget splits the CSV column on ; and delegates parsing of each
    token to CourseWidget, creating courses on the fly when needed.
    """

    def __init__(self):
        super().__init__(Course, separator=";", field="code")
        self.course_w = CourseWidget()

    def clean(self, value, row=None, *args, **kwargs) -> list[Course]:
        """Returns a list of Course instances parsed from the provided CSV value.

        If value is empty or missing, returns an empty list (no courses associated).
        """
        if not value:
            return []

        courses = []
        for token in value.split(self.separator):
            token = token.strip()
            if token:
                # Delegate to CourseCodeWidget to parse/create individual course
                course = self.course_w.clean(token, row)
                if course:
                    courses.append(course)

        return courses


class CourseCodeWidget(widgets.ForeignKeyWidget):
    """Resolve a course code  into a Course.

    A Course code is <college_code>-<dept_code><course_no>.
    """

    def __init__(self):
        super().__init__(Course, field="code")
        self.department_w = DepartmentWidget()

    def clean(
        self, value, row=None, credit_field: str | None = None, *args, **kwargs
    ) -> Course | None:
        """Return a Course object matching the provided value.

        value example formats:
          - "AGR121" (implies college from row or "COAS")
          - "CAFS-AGR121" (explicit dept AGR from CAFS college)

        If course, college or department do not exist they will be created,
        otherwise the existing course is returned (and updated when fields differ).
        """
        if not value:
            return None

        dept_code, course_no, college_code = expand_course_code(value, row=row)
        dept = self.department_w.clean(dept_code, row)

        # course_code = make_course_code(dept, course_no)

        title_raw = row.get("course_title") if row else None

        course, _ = Course.objects.get_or_create(
            department=dept,
            course_no=course_no,
        )
        # defaults are ignore in case of existance
        # since we want to update in all case, just doing it.
        if title_raw and course.title != title_raw:
            course.title = title_raw
            course.save(update_fields=["title"])

        return course


class CollegeWidget(widgets.ForeignKeyWidget):
    """Return or create the College referenced by college_code."""

    def __init__(self):
        # field is a Model attribute used to identify uniquely the instances.
        # if not set then default to pk
        super().__init__(College, field="code")

    def clean(self, value, row=None, *args, **kwargs) -> College:
        """Return or create the College referenced by college_code.

        Defaults to COAS.
        """
        code = (value or "COAS").strip().upper()
        college, _ = College.objects.get_or_create(code=code)

        return college


class DepartmentWidget(widgets.ForeignKeyWidget):
    """Return or create the Department referenced by course_dept and college_code."""

    def __init__(self):
        super().__init__(Department, field="code")
        self.college_w = CollegeWidget()

    def clean(self, value, row=None, *args, **kwargs) -> Department:
        """Return or create the Department using course_dept and college_code.

        If nothing passed, return a default value.
        """
        dept_short_name = (value or "").strip().upper()
        if not dept_short_name:
            return Department.get_default()

        college = self.college_w.clean((row.get("college_code") or "").strip())

        department, _ = Department.objects.get_or_create(
            short_name=dept_short_name, college=college
        )
        return department
