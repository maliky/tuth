"""Wgts module."""

from typing import Any, Optional

from django.db import IntegrityError
from import_export import widgets

from app.academics.choices import COLLEGE_LONG_NAME
from app.academics.models.college import College
from app.academics.models.concentration import Major
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.department import Department
from app.academics.models.curriculum_course import CurriCrs
from app.academics.utils import (
    expand_crs_code,
    normalize_college_code,
    normalize_dpt_code,
)
from app.registry.models import CreditHour
from app.academics.ensures import (
    ensure_college,
    ensure_crs,
    ensure_curri,
    ensure_curri_crs,
    ensure_dpt,
)
from app.shared.utils import asserts_keys, get_in_row, parse_str, to_int


class CurriCrsWgt(widgets.ForeignKeyWidget):
    """Create or CurriCrs from CSV rows.

    Use the curriculum_short name as the 'value'.
    The widget delegates curriculum parsing to CurriWgt and course parsing
    to CrsWgt then assembles a CurriCrs object from the results.
    """

    def __init__(self):
        super().__init__(CurriCrs)
        self.curriculum_w = CurriWgt()
        self.course_w = CrsWgt()

    def clean(self, value, row=None, *args, **kwargs) -> CurriCrs:
        """Assemble course_dept, curriculum and course to return a curriculum course."""
        # we don't use value.  We always get a curriculum course back

        asserts_keys(["course_no", "dept_code"], row)

        curriculum = self.curriculum_w.clean(value=value, row=row)
        if curriculum is None:
            curriculum = Curriculum.get_dft()
        course = self.course_w.clean(value=None, row=row)

        credit_hours_val = to_int(get_in_row("credit_hours", row))
        credit_hours, _ = CreditHour.objects.get_or_create(code=credit_hours_val)

        is_required = (
            True
            if get_in_row("is_required", row) in {"1", "true", "yes", "required"}
            else False
        )

        return ensure_curri_crs(
            curriculum=curriculum,
            course=course,
            credit_code=credit_hours.code,
            is_required=is_required,
        )


class CurriWgt(widgets.ForeignKeyWidget):
    """Look up or create a Curriculum from a short name.

    The associated college is determined from row['college_code'] when
    present. Missing curricula are created automatically.
    """

    SHORT_NAME_MAX = Curriculum._meta.get_field("short_name").max_length

    def __init__(self, fuzzy_threshold: float = 1):
        # set the look_up field to uniquely identify the Curriculum to short_name.
        self.fuzzy_threshold = fuzzy_threshold
        super().__init__(Curriculum, field="short_name")
        self.college_w = CollegeWgt()

    def clean(
        self, value, row=None, fuzzy_threshold: float = 1.0, *args, **kwargs
    ) -> Curriculum | None:
        """Returns a Curriculum object matching the provided short_name in value.

        Example input row:
          - row["curriculum"] = "Bsc Agriculture"
          - row["college_code"] = "CAFS"
        """

        curr_value = parse_str(value)
        college = ensure_college(get_in_row("college_code", row))

        if not curr_value:
            return Curriculum.get_dft(def_college=college)

        curriculum = ensure_curri(
            curr_value, college=college, fuzzy_threshold=fuzzy_threshold
        )

        return curriculum


class CrsWgt(widgets.ForeignKeyWidget):
    """Convert course_* CSV columns into a Course.

    course_dept and course_no identify the course while college is
    optional and defaults to "COAS". Results are cached to avoid duplicate
    queries when several rows reference the same course.
    """

    def __init__(self):
        super().__init__(Course, field="code")
        self.department_w = DptWgt()
        self.college_w = CollegeWgt()

    def clean(
        self,
        value: Any,
        row: Optional[dict[str, Any]] = None,
        fuzzy_threshold: float = 1,
        *args: Any,
        **kwargs: Any,
    ) -> Course:
        """Return a Course gotten from dept, no and college_code.

        Value is ignored (import-export still passes the column declared in
        the resource, but the info we need is spread across *row*).
        """
        course_no = get_in_row("course_no", row)
        dept_code = get_in_row("dept_code", row)

        if not course_no or not dept_code:
            return Course.get_unique_dft()

        college_code = get_in_row("college_code", row)
        college = ensure_college(college_code)  # verifier que 9a ne fait pas de doublons
        department = ensure_dpt(dept_code, college)  # idem

        title = get_in_row("course_title", row)

        crs_obj = ensure_crs(
            department=department,
            course_no=course_no,
            title=title,
            fuzzy_threshold=fuzzy_threshold,
        )
        return crs_obj


class CrsManyWgt(widgets.ManyToManyWidget):
    """Parse list_courses and return a list of Course objects.

    The widget splits the CSV column on ; and delegates parsing of each
    token to CrsWgt, creating courses on the fly when needed.
    """

    def __init__(self):
        super().__init__(Course, separator=";", field="code")
        self.course_w = CrsWgt()

    def clean(self, value, row=None, *args, **kwargs) -> list[Course]:
        """Returns a list of Course instances parsed from the provided CSV value.

        If value is empty or missing, returns an empty list (no courses associated).
        """
        if not value:
            return []

        courses = []
        for token in str(value).split(self.separator):
            token = token.strip()
            if token:
                # Delegate to CrsCodeWgt to parse/create individual course
                course = self.course_w.clean(token, row)
                if course:
                    courses.append(course)

        return courses

    def render(self, value, obj=None, **kwargs):
        """Return course codes joined with ':' for exports."""
        if not value:
            return ""

        if hasattr(value, "all"):
            iterable = value.all()
        else:
            iterable = value

        codes = [getattr(course, self.field) for course in iterable if course]
        return self.separator.join(codes)


class CrsCodeWgt(widgets.ForeignKeyWidget):
    """Resolve a course code  into a Course.

    A Course code is <college_code>-<dept_code><course_no>.
    """

    def __init__(self):
        super().__init__(Course, field="code")
        self.department_w = DptWgt()

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

        dept_code, course_no, college_code = expand_crs_code(value, row=row)
        dept = self.department_w.clean(dept_code, row)

        # course_code = make_crs_code(dept, course_no)

        title_raw = row.get("course_title") if row else None

        course, _ = Course.objects.get_or_create(
            department=dept,
            number=course_no,
        )
        # defaults are ignore in case of existance
        # since we want to update in all case we do it manualy.
        if title_raw and course.title != title_raw:
            course.title = title_raw
            course.save(update_fields=["title"])

        return course


class CollegeWgt(widgets.ForeignKeyWidget):
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
        code = normalize_college_code(parse_str(value))
        college, _ = College.objects.get_or_create(
            code=code, defaults={"long_name": COLLEGE_LONG_NAME.get(code.lower(), "deft")}
        )

        return college


class DptWgt(widgets.ForeignKeyWidget):
    """Return or create the Department referenced by course_dept and college_code."""

    def __init__(self):
        super().__init__(Department, field="code")
        self.college_w = CollegeWgt()

    def clean(self, value, row=None, *args, **kwargs) -> Department:
        """Return or create the Department using course_dept and college_code.

        If nothing passed, return a default value.
        """
        if not value:
            return Department.get_dft()

        dept_code = normalize_dpt_code(parse_str(value))

        college = self.college_w.clean(get_in_row("college_code", row))

        department, _ = Department.objects.get_or_create(code=dept_code, college=college)
        return department
