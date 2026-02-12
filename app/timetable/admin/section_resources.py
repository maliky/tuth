"""Import/export resources for section models."""

from import_export import fields, resources

from app.academics.admin.widgets import CurriCourseWgt
from app.people.admin.widgets import FacultyUsernameWgt
from app.timetable.admin.core_widgets import SemesterWgt
from app.timetable.models.section import Section


class SectionResource(resources.ModelResource):

    # just to keep it in headers and accessible for other.

    academic_year = fields.Field(attribute=None, column_name="academic_year")
    course_no = fields.Field(attribute=None, column_name="course_no")
    course_dept = fields.Field(attribute=None, column_name="course_dept")
    dept_code = fields.Field(attribute=None, column_name="dept_code")
    college_code = fields.Field(attribute=None, column_name="college_code")

    # for this section, it is mandatory that the semester be attached to a year
    # when exporting we should export the semester_code
    semester = fields.Field(
        attribute="semester",
        column_name="semester_no",
        widget=SemesterWgt(),
    )
    curriculum_course = fields.Field(
        # could be other course columns
        attribute="curriculum_course",
        column_name="curriculum",
        widget=CurriCourseWgt(),
    )
    number = fields.Field(attribute="number", column_name="section_no")

    faculty = fields.Field(
        column_name="faculty",
        attribute="faculty",
        widget=FacultyUsernameWgt(),
    )

    class Meta:
        model = Section
        import_id_fields = ("semester", "curriculum_course", "number")
        fields = (
            "number",
            "curriculum_course",
            "semester",
            "faculty",
            "course_dept",
            "dept_code",
            "academic_year",
            "course_no",
            "college_code",
        )
        skip_unchanged = True
        use_bulk = False

    def dehydrate_semester(self, obj):
        semester = getattr(obj, "semester", None)
        return getattr(semester, "number", "") if semester else ""

    def dehydrate_academic_year(self, obj):
        semester = getattr(obj, "semester", None)
        academic_year = getattr(semester, "academic_year", None)
        return getattr(academic_year, "code", "") if academic_year else ""

    def dehydrate_curriculum_course(self, obj):
        curriculum = getattr(obj.curriculum_course, "curriculum", None)
        return getattr(curriculum, "short_name", "") if curriculum else ""

    def dehydrate_course_no(self, obj):
        course = getattr(obj.curriculum_course, "course", None)
        return getattr(course, "number", "") if course else ""

    def dehydrate_course_dept(self, obj):
        course = getattr(obj.curriculum_course, "course", None)
        department = getattr(course, "department", None)
        return getattr(department, "code", "") if department else ""

    def dehydrate_dept_code(self, obj):
        return self.dehydrate_course_dept(obj)

    def dehydrate_college_code(self, obj):
        course = getattr(obj.curriculum_course, "course", None)
        department = getattr(course, "department", None)
        college = getattr(department, "college", None)
        return getattr(college, "code", "") if college else ""

    def dehydrate_faculty(self, obj):
        faculty = getattr(obj, "faculty", None)
        staff = getattr(faculty, "staff_profile", None) if faculty else None
        return getattr(staff, "username", "") if staff else ""
