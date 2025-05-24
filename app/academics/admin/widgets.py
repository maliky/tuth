from import_export import widgets
from app.academics.models.college import College
from app.academics.models.course import Course
from app.shared.management.populate_helpers.curriculum import extract_code


class CourseWidget(widgets.ForeignKeyWidget):
    """Return or create a :class:`Course` from its code and row college."""

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        dept_code, course_num = extract_code(value)
        college_code = row.get("college") if row else None
        college = None
        if college_code:
            college, _ = College.objects.get_or_create(
                code=college_code,
                defaults={"fullname": college_code},
            )
        course, _ = Course.objects.get_or_create(
            name=dept_code,
            number=course_num,
            college=college,
            defaults={"title": value},
        )
        return course
