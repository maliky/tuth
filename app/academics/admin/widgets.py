"""Widgets module."""

from typing import Any, Optional

from import_export import widgets

from app.academics.choices import COLLEGE_CODE, COLLEGE_LONG_NAME
from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.academics.models.program import Program
from app.shared.models import CreditHour
from app.shared.utils import expand_course_code, get_in_row


class ProgramWidget(widgets.ForeignKeyWidget):
    """Create or Program from CSV rows.

    Use the curriculum_short name as the 'value'.
    The widget delegates curriculum parsing to CurriculumWidget and course parsing
    to CourseWidget then assembles a Program object from the results.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(Program)
        self.curriculum_w = CurriculumWidget()
        self.course_w = CourseWidget()

    def clean(self, value, row=None, *args, **kwargs) -> Program:
        """Assemble course_dept, curriculum and course to return a curriculum course."""

        # we don't use value.  We always get a course back
        course = self.course_w.clean(value=None, row=row)

        curriculum = (
            self.curriculum_w.clean(value=value, row=row)
            if value
            else Curriculum.get_default()
        )

        credit_hours, _ = CreditHour.objects.get_or_create(
            code=get_in_row("credit_hours", row)
        )
        program, _ = Program.objects.get_or_create(
            curriculum=curriculum,
            course=course,
            defaults={
                "credit_hours": credit_hours,
                "is_required": get_in_row("is_required", row),
            },
        )
        return program


class CurriculumWidget(widgets.ForeignKeyWidget):
    """Look up or create a Curriculum from a short name.

    The associated college is determined from row['college_code'] when
    present. Missing curricula are created automatically.
    """

    def __init__(self):
        # set the look_up field to uniquely identify the Curriculum to short_name.
        super().__init__(Curriculum, field="short_name")
        self.college_w = CollegeWidget()

    def clean(self, value, row=None, *args, **kwargs) -> Curriculum | None:
        """Returns a Curriculum object matching the provided short_name in value.

        Example input row:
          - row["curriculum"] = "Bsc Agriculture"
          - row["college_code"] = "CAFS" (optional, defaults to "COAS")

        Automatically creates curriculum with today's date.
        """
        if not value:
            return Curriculum.get_default()

        short_name = value.strip()

        college_code = get_in_row("college_code", row)
        college = self.college_w.clean(college_code)

        curriculum, _ = Curriculum.objects.get_or_create(
            short_name=short_name,
            defaults={
                "long_name": short_name,
                "college": college,
            },
        )

        return curriculum


class CourseWidget(widgets.ForeignKeyWidget):
    """Convert course_* CSV columns into a Course.

    course_dept and course_no identify the course while college is
    optional and defaults to "COAS". Results are cached to avoid duplicate
    queries when several rows reference the same course.
    """

    def __init__(self):
        super().__init__(Course, field="code")
        self.department_w = DepartmentWidget()
        self.college_w = CollegeWidget()

    def clean(
        self,
        value: Any,
        row: Optional[dict[str, Any]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Course:
        """Return a Course gotten from dept, no and college_code.

        Value is ignored (import-export still passes the column declared in
        the resource, but the info we need is spread across *row*).
        """
        course_no = get_in_row("course_no", row)
        course_dept = get_in_row("course_dept", row)

        if not course_no or not course_dept:
            return Course.get_unique_default()

        course, _ = Course.objects.get_or_create(
            number=course_no,
            department=self.department_w.clean(course_dept, row),
        )
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
        Accept 'CBA', 'CAFS', '', 'CHS', 'EDRCE', 'CET', 'CAS' and COAS, COED
        COET COBA but normalise the code to 4 letters
        """
        code = COLLEGE_CODE.get((value or "").strip().lower(), "DEFT")
        college, _ = College.objects.get_or_create(
            code=code, defaults={"long_name": COLLEGE_LONG_NAME.get(code.lower(), "deft")}
        )

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
        if not value:
            return Department.get_default()

        dept_short_name = (value or "").strip().upper()

        college = self.college_w.clean((row.get("college_code") or "").strip())

        department, _ = Department.objects.get_or_create(
            short_name=dept_short_name, college=college
        )
        return department
