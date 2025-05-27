from import_export import widgets
from app.academics.models.college import College
from app.academics.models.course import Course
from app.shared.utils import expand_course_code


class CourseManyWidget(widgets.ManyToManyWidget):
    """
    Parse the `list_courses` column (semicolon-separated list of codes),
      auto-create missing Course rows exactly like Section import does.
    """

    def __init__(self):
        # use the same separator everywhere
        super().__init__(Course, separator=";", field="code")
        # re-use the existing single-course widget for DRYness
        self._cw = CourseWidget(model=Course, field="code")

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return []  # keep M2M empty
        courses = []
        for token in value.split(self.separator):
            token = token.strip()
            if token:
                # propagate row – it contains "college"
                courses.append(self._cw.clean(token, row))
        return courses


class CourseWidget(widgets.ForeignKeyWidget):
    """Return or create a :class:`Course` from its code and row college."""

    def clean(self, value, row=None, *args, **kwargs):
        """Return the Course object described by ``value``.

        ``value`` may include the college code after a hyphen.  When omitted,
        the college is taken from ``row['college']`` or defaults to ``"COAS"``.
        """

        if not value:
            return None

        name, number, college_code = expand_course_code(value, row=row)

        college, _ = College.objects.get_or_create(
            code=college_code,
            defaults={"fullname": college_code},
        )

        # find existing course(s) for this triple
        qs = Course.objects.filter(name=name, number=number, college=college)
        count = qs.count()
        code = f"{name}{number}"
        if count > 1:
            raise ValueError(
                f"Integrity Error: Multiple courses found for {code} in {college_code}"
            )
        if count == 0:
            course = Course.objects.create(
                name=name,
                number=number,
                college=college,
                credit_hours=3,
                title=value,
            )
        else:
            course = qs.get()
        return course


class CollegeWidget(widgets.ForeignKeyWidget):
    """Return or create a :class:`College` from its code."""

    def clean(self, value, row=None, *args, **kwargs):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._resource = None  # will be injected by Resource below

        if not value:
            return None
        obj, created = College.objects.get_or_create(
            code=value,
            defaults={"fullname": value},
        )
        if created and self._resource:  # resource back-reference present
            self._resource._new_colleges.add(value)
        return obj
