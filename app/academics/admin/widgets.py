"""Widgets module."""

from typing import Any, Optional, cast

from import_export import widgets

from app.academics.models import College, Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriculumCourse
from app.academics.models.department import Department
from app.shared.utils import expand_course_code, make_course_code


class CurriculumCourseWidget(widgets.ForeignKeyWidget):
    """Create or fetch CurriculumCourse rows from CSV data.

    The widget delegates curriculum and course parsing to CurriculumWidget
    and CourseWidget then assembles a :class:CurriculumCourse instance from
    the results.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(CurriculumCourse)
        self.curriculm_w = CurriculumWidget()
        self.course_w = CourseWidget()

    def clean(self, value, row=None, *args, **kwargs) -> CurriculumCourse | None:
        """Assemble course_dept, curriculum and course to return a curriculum course."""
        if not value:
            return None

        curriculum = cast(
            Curriculum, self.curriculm_w.clean(value=value.strip(), row=row)
        )

        course_dept_value = row.get("course_dept", "").strip()
        course = self.course_w.clean(value=course_dept_value, row=row)

        curriculum_course, _ = CurriculumCourse.objects.get_or_create(
            curriculum=curriculum,
            course=course,
            credit_hours=row.get("credit_hours", "").strip(),
            is_required=row.get("is_required", True).strip(),
        )
        return curriculum_course


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

        college_code = (row.get("college_code") or "").strip()
        college = self.college_w.clean(college_code)

        key = (course_dept, course_no, college_code)
        if key in self._cache:
            return self._cache.get(key)

        code = make_course_code(course_dept, course_no)  # e.g. AGR121

        course, course_created = Course.objects.get_or_create(
            number=course_no,
            college=college,
            defaults={"title": row.get("course_title", code)},
        )

        if department and not course.departments.filter(pk=department.pk).exists():
            course.departments.add(department)

        self._cache[key] = course
        return course


class CourseManyWidget(widgets.ManyToManyWidget):
    """Parse list_courses and return a list of :class:Course objects.

    The widget splits the CSV column on ; and delegates parsing of each
    token to :class:CourseWidget, creating courses on the fly when needed.
    """

    def __init__(self):
        # Uses ";" as a separator between multiple course codes.
        super().__init__(Course, separator=";", field="code")
        # Delegates the parsing and creation of individual courses to CourseCodeWidget.
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
    """Resolve a course code into a :class:Course.

    Supports optional -<college> suffixes and falls back to
    row['college'] or "COAS" when the suffix is absent. New courses are
    created automatically with data from the import row.
    """

    def __init__(self):
        super().__init__(Course, field="code")
        self.department_w = DepartmentWidget()
        self.college_w = CollegeWidget()

    def clean(
        self, value, row=None, credit_field: str | None = None, *args, **kwargs
    ) -> Course | None:
        """Return a Course object matching the provided value.

        The optional credit_field argument specifies the CSV column used for
        credit hours when creating or updating a course.

        value example formats:
          - "AGR121" (implies college from row or "COAS")
          - "AGR121-CFAS" (explicit college code CFAS)

        If the course does not exist it will be created, otherwise the existing
        course is returned (and updated when fields differ).
        """
        if not value:
            return None

        dept_code, number, college_code = expand_course_code(value, row=row)
        course_code = make_course_code(dept_code, number, college_code)

        department = self.department_w.clean(dept_code)
        college = self.college_w.clean(college_code)

        qs = Course.objects.filter(code=course_code, college=college)
        count = qs.count()

        if count > 1:
            raise ValueError(
                f"Integrity Error: Multiple courses found for {course_code} in college {college_code}"
            )

        # Pull optional data from the row
        credit_hours = (row.get("credit_hours") or "").strip()  # always str for mypy
        title_raw = row.get("course_title") if row else None

        if count == 0:
            # Create a new course with info from the row (credits default to 3)
            credit_hours = int(credit_hours) if credit_hours.isdigit() else 3

            course = Course.objects.create(
                number=number,
                college=cast(College, college),
                credit_hours=credit_hours,
                title=title_raw or value,
            )
            if department and not course.departments.filter(pk=department.pk).exists():
                course.departments.add(department)

        else:
            course = qs.get()
            updated = False
            if title_raw and course.title != title_raw:
                course.title = title_raw
                updated = True
            if credit_hours and str(credit_hours).strip().isdigit():
                cr_val = int(credit_hours)
                if cr_val != course.credit_hours:
                    course.credit_hours = cr_val
                    updated = True
            if updated:
                course.save(update_fields=["title", "credit_hours"])

        return course


class CollegeWidget(widgets.ForeignKeyWidget):
    """Return or create the College referenced by college_code."""

    def __init__(self):
        super().__init__(College, field="code")

    def clean(self, value, row=None, *args, **kwargs) -> College | None:
        """Return or create the College referenced by college_code."""
        if not value:
            return None

        code = (value or "COAS").strip().upper()
        college, _ = College.objects.get_or_create(code=code)

        return college


class DepartmentWidget(widgets.ForeignKeyWidget):
    """Return or create the Department referenced by course_dept and college_code."""

    def __init__(self):
        super().__init__(Department, field="course_dept")
        self.college_w = CollegeWidget()

    def clean(self, value, row=None, *args, **kwargs) -> Department | None:
        """Return or create the Department referenced by course_dept and college_code."""
        if not value:
            return None
        dept_code = value.strip().upper()

        college_code = (row.get("college_code") or "").strip()
        college = self.college_w.clean(college_code)

        department, _ = Department.objects.get_or_create(code=dept_code, college=college)
        return department


class DepartmentManyWidget(widgets.ManyToManyWidget):
    """Parse list_dept and return a list of :class:Deparments objects.

    The widget splits the CSV column on ; and delegates parsing of each
    token to :class:CourseWidget, creating courses on the fly when needed.
    """

    def __init__(self):
        super().__init__(Department, separator=";", field="code")
        self.department_w = CourseWidget()

    def clean(self, value, row=None, *args, **kwargs) -> list[Course]:
        """Returns a list of Departments instances parsed from the provided CSV value.

        If value is empty or missing, returns an empty list (no departement associated).
        """
        if not value:
            return []

        departements = []
        for token in value.split(self.separator):
            token = token.strip()
            if token:
                dept = self.department_w.clean(token, row)
                if dept:
                    departements.append(dept)

        return departements
