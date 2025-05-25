from import_export import widgets
from app.academics.models.college import College
from app.academics.models.course import Course
from app.shared.utils import expand_course_code


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
            )
        else:
            course = qs.get()
        return course
