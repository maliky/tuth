"""Widgets module."""

from typing import Any, Optional

from import_export import widgets

from app.academics.models import College, Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.curriculum_course import CurriculumCourse
from app.shared.utils import expand_course_code, make_course_code

# no need for a CollegeWidget, user foreignkeywidget


class CurriculumCourseWidget(widgets.ForeignKeyWidget):
    """
    Create a CurriculumCourse line based on :
    - the curriculum short name and
    - the course code, number and college
    """

    def __init__(self, *args, **kwargs):
        super().__init__(CurriculumCourse)
        self.curriculm_w = CurriculumWidget()
        self.course_w = CourseWidget()

    def clean(self, value, row=None, *args, **kwargs) -> CurriculumCourse | None:
        if not value:
            return None

        curriculum = self.curriculm_w.clean(value=value.strip(), row=row)

        course_name_value = row.get("course_name", "").strip()
        course = self.course_w.clean(value=course_name_value, row=row)

        curriculum_course, _ = CurriculumCourse.objects.get_or_create(
            curriculum=curriculum,
            course=course,
            credit_hours=row.get("credit_hours", "").strip(),
            is_required=row.get("is_required", True).strip(),
        )
        return curriculum_course


class CurriculumWidget(widgets.ForeignKeyWidget):
    """
    Widget to find or create a Curriculum instance given its short_name.

    Associates the curriculum to a college explicitly provided in `row['college']`
    """

    def __init__(self):
        super().__init__(Curriculum, field="short_name")

    def clean(self, value, row=None, *args, **kwargs) -> Curriculum | None:
        """
        Returns a Curriculum object matching the provided short_name in value

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
    """
    Accept three separate columns – course_name (dept), course_no (num),
    and college – and return or create the matching Course instance.

    Expected CSV columns in the *row* dict
    --------------------------------------
    * ``course_name``  – department part (e.g. "AGR")
    * ``course_no``    – number part     (e.g. "121")
    * ``college``      – college code    (e.g. "CAFS") – optional

    If *college* is empty, defaults to ``"COAS"``.

    Lookups are cached so repeated rows referencing the same course do not hit
    the database multiple times.
    """

    def __init__(self):
        super().__init__(Course, field="code")
        self._cache: dict[tuple[str, str, str], Course] = {}

    def clean(
        self,
        value: Any,
        row: Optional[dict[str, Any]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Optional[Course]:
        """
        *value* is ignored (import-export still passes the column declared in
        the resource, but the info we need is spread across *row*).
        """
        if row is None:
            return None
        # import pdb; pdb.set_trace()
        course_name = row.get("course_name", "").strip().upper()
        course_no = row.get("course_no", "").strip()

        if not course_name or not course_no:
            return None

        college_code = row.get("college_code", "COAS").strip().upper()

        key = (course_name, course_no, college_code)
        if key in self._cache:
            return self._cache[key]

        # ── get or create the College ─────────────────────────────
        college, college_created = College.objects.get_or_create(code=college_code)
        if college_created:
            college.save()

        # ── get or create the Course ──────────────────────────────
        code = make_course_code(course_name, course_no)  # e.g. AGR121
        course, course_created = Course.objects.get_or_create(
            name=course_name,
            number=course_no,
            college=college,
            defaults={"title": row.get("course_title", code)},
        )
        if course_created:
            course.save()
        self._cache[key] = course
        return course


class CourseManyWidget(widgets.ManyToManyWidget):
    """
    Parses the `list_courses` column from CSV input, which should be
    a semicolon-separated list of course codes. Automatically creates
    Course objects if they don't exist yet, using the logic defined in
    the CourseCodeWidget.
    """

    def __init__(self):
        """
        Initialize the widget:
        - Uses ";" as a separator between multiple course codes.
        - Delegates the parsing and creation of individual courses to CourseCodeWidget.
        """
        super().__init__(Course, separator=";", field="code")
        self._cw = CourseWidget()

    def clean(self, value, row=None, *args, **kwargs) -> list[Course]:
        """
        Returns a list of Course instances parsed from the provided CSV value.

        If `value` is empty or missing, returns an empty list (no courses associated).
        """
        if not value:
            return []

        courses = []
        for token in value.split(self.separator):
            token = token.strip()
            if token:
                # Delegate to CourseCodeWidget to parse/create individual course
                course = self._cw.clean(token, row)
                if course:
                    courses.append(course)

        return courses


class CourseCodeWidget(widgets.ForeignKeyWidget):
    """
    Widget to find or create a Course instance given a course code.

    The course code can optionally include a college code suffix separated by a hyphen.
    If the college code is not provided explicitly, it defaults to the value from
    `row['college']` or "COAS".
    """

    def __init__(self):
        super().__init__(Course, field="code")

    def clean(
        self, value, row=None, credit_field: str | None = None, *args, **kwargs
    ) -> Course | None:
        """
        Return a Course object matching the provided value.
        The optional ``credit_field`` argument specifies the CSV column used for
        credit hours when creating or updating a course.

        ``value`` example formats:
          - ``"AGR121"`` (implies college from row or ``"COAS"``)
          - ``"AGR121-CFAS"`` (explicit college code CFAS)

        If the course does not exist it will be created, otherwise the existing
        course is returned (and updated when fields differ).
        """
        if not value:
            return None

        name, number, college_code = expand_course_code(value, row=row)

        # Get or create the college
        college, _ = College.objects.get_or_create(
            code=college_code,
        )

        # Check for existing course
        qs = Course.objects.filter(name=name, number=number, college=college)
        count = qs.count()
        code = f"{name}{number}"

        if count > 1:
            raise ValueError(
                f"Integrity Error: Multiple courses found for {code} in college {college_code}"
            )

        # Pull optional data from the row
        cr_raw: str = (row.get("credit_hours") or "").strip()  # always str for mypy
        title_raw = row.get("course_title") if row else None

        if count == 0:
            # Create a new course with info from the row (credits default to 3)
            credit_hours = int(cr_raw) if cr_raw.isdigit() else 3

            course = Course.objects.create(
                name=name,
                number=number,
                college=college,
                credit_hours=credit_hours,
                title=title_raw or value,
            )
        else:
            course = qs.get()
            updated = False
            if title_raw and course.title != title_raw:
                course.title = title_raw
                updated = True
            if cr_raw and str(cr_raw).strip().isdigit():
                cr_val = int(cr_raw)
                if cr_val != course.credit_hours:
                    course.credit_hours = cr_val
                    updated = True
            if updated:
                course.save(update_fields=["title", "credit_hours"])

        return course


class CollegeWidget(widgets.ForeignKeyWidget):
    """Simple FK helper so we can import `college_code` if present."""

    def __init__(self):
        super().__init__(College, field="code")

    def clean(self, value, row=None, *args, **kwargs) -> College | None:
        if not value:
            return None
        code = (value or "COAS").strip().upper()
        college, _ = College.objects.get_or_create(code=code)
        return college
