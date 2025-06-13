"""Import/export resources for timetable models. (Section)"""

from typing import Any
from import_export import fields, resources

from app.academics.admin.widgets import CourseWidget
from app.people.admin.widgets import FacultyWidget
from app.timetable.admin.widgets import SemesterWidget
from app.timetable.models.section import Section


class SectionResource(resources.ModelResource):

    # just to keep it in headers and accessible for other.
    academic_year = fields.Field(column_name="academic_year", attribute=None)
    course_no = fields.Field(column_name="course_no", attribute=None)
    college_code = fields.Field(column_name="college_code", attribute=None)

    # for this section, it is mandatory that the semester be attached to a year
    # when exporting we should export the semester_code
    semester = fields.Field(
        column_name="semester_no",
        attribute="semester",
        widget=SemesterWidget(),
    )
    course = fields.Field(
        # could be other course columns
        column_name="course_name",
        attribute="course",
        widget=CourseWidget(),
    )
    number = fields.Field(column_name="section_no", attribute="number")

    faculty = fields.Field(
        column_name="faculty",
        attribute="faculty",
        widget=FacultyWidget(),
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        pass

    def before_import(self, dataset, **kwargs):
        super().before_import(dataset, **kwargs)
        pass

    # def save_instance(self, instance,  is_create, row, **kwargs):
    #     # import ipdb; ipdb.set_trace()
    #     try:
    #         super().save_instance(instance,  is_create, row, **kwargs)
    #     except Exception as exc:
    #         print("Integrity Error on Row:", row)
    #         print("Instance values:")
    #         print("course:", instance.course, instance.course.pk)
    #         print("faculty:", instance.faculty, instance.faculty.pk)
    #         print("semester:", instance.semester, instance.semester.pk)
    #         import ipdb; ipdb.set_trace()
    #         raise exc

    class Meta:
        model = Section
        import_id_fields = ("semester", "number", "course", "faculty")
        fields = (
            "number",
            "course",
            "semester",
            "faculty",
            "academic_year",
            "course_no",
            "college_code",
        )
        skip_unchanged = True
        use_bulk = False
