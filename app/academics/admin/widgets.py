"""Widgets module."""

from datetime import date

from import_export import widgets

from app.academics.models import College, Course, Curriculum
from app.shared.utils import expand_course_code


class CourseManyWidget(widgets.ManyToManyWidget):
    """
    Parses the `list_courses` column from CSV input, which should be
    a semicolon-separated list of course codes. Automatically creates
    Course objects if they don't exist yet, using the logic defined in
    the CourseWidget.
    """

    def __init__(self):
        """
        Initialize the widget:
        - Uses ";" as a separator between multiple course codes.
        - Delegates the parsing and creation of individual courses to CourseWidget.
        """
        super().__init__(Course, separator=";", field="code")
        self._cw = CourseWidget(model=Course, field="code")

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
                # Delegate to CourseWidget to parse/create individual course
                course = self._cw.clean(token, row)
                if course:
                    courses.append(course)

        return courses


class CourseWidget(widgets.ForeignKeyWidget):
    """
    Widget to find or create a Course instance given a course code.

    The course code can optionally include a college code suffix separated by a hyphen.
    If the college code is not provided explicitly, it defaults to the value from
    `row['college']` or "COAS".
    """

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
            defaults={"fullname": college_code},
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
        cr_raw = row.get(credit_field) if row else None
        title_raw = row.get("course_title") if row else None

        if count == 0:
            # Create a new course with info from the row (credits default to 3)
            credit_hours = int(cr_raw) if str(cr_raw).strip().isdigit() else 3

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
    """
    Widget to find or create a College instance given a college code.

    Automatically tracks newly created colleges for reporting purposes.
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes the widget and sets a placeholder (`_resource`) for
        back-reference to the parent import resource (if provided).
        """
        super().__init__(*args, **kwargs)
        self._resource = None  # Will be injected by the resource using this widget

    def clean(self, value, row=None, *args, **kwargs) -> College | None:
        """
        Returns a College object matching the provided code.

        If the college does not exist, it is automatically created with a default name
        equal to its code. Newly created colleges are logged via `_resource` if available.
        """
        if not value:
            return None

        college, created = College.objects.get_or_create(
            code=value,
            defaults={"fullname": value},
        )

        if created and self._resource:
            # Log newly created college for import summary
            self._resource._new_colleges.add(value)

        return college


class CurriculumWidget(widgets.ForeignKeyWidget):
    """
    Widget to find or create a Curriculum instance given its short_name.

    Associates the curriculum to a college explicitly provided in `row['college']`
    or defaults to "COAS" if none is provided. Checks integrity to avoid conflicts
    where the same curriculum short_name exists in a different college.
    """

    def clean(self, value, row=None, *args, **kwargs) -> Curriculum | None:
        """
        Returns a Curriculum object matching the provided short_name.

        Example input row:
          - row["curriculum"] = "Bsc Agriculture"
          - row["college"] = "CFAS" (optional, defaults to "COAS")

        Automatically creates curriculum with today's date and provided college if it
        does not already exist.
        """
        if not value:
            return None

        college_code = (row.get("college") or "COAS").strip()
        college, _ = College.objects.get_or_create(
            code=college_code,
            defaults={"fullname": college_code},
        )

        curriculum, created = Curriculum.objects.get_or_create(
            short_name=value.strip(),
            defaults={
                "title": value.strip(),
                "college": college,
                "creation_date": date.today(),
            },
        )

        if not created and curriculum.college != college:
            raise ValueError(
                f"Integrity Error: Curriculum '{curriculum.short_name}' already exists "
                f"in college '{curriculum.college.code}', but attempted to associate "
                f"with college '{college.code}'."
            )

        return curriculum
