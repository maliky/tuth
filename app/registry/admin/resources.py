"""Resource module for the registry."""

from import_export import fields, resources

from app.people.admin.widgets import StdGradeWgt, StdUserWgt
from app.registry.admin.resources_mapping import GRADE_HEADER_MAP
from app.registry.admin.widgets import GradeValueWgt
from app.registry.models.grade import Grade, GradeValue
from app.registry.models.registration import Registration
from app.shared.utils import get_in_row
from app.timetable.admin.resource_mapping import SECTION_HEADER_MAP
from app.timetable.admin.section_widgets import SecWgt
from app.timetable.utils import normalize_academic_year


class GradeResource(resources.ModelResource):
    """Import grades from a flat csv file.

    Requires: student_id, grade_code, academic_year, semester_no,
    college_code, dept_no, course_no, credit_hours, section_no,curriculum.
    """

    # check the Widget
    student = fields.Field(
        column_name="student_id",
        attribute="student",
        widget=StdUserWgt(),
    )
    student_name = fields.Field(attribute=None, column_name="student_name")
    section = fields.Field(
        column_name="section_no",
        attribute="section",
        widget=SecWgt(fuzzy_threshold=1.0),
    )
    curriculum = fields.Field(attribute=None, column_name="curriculum")
    course_no = fields.Field(attribute=None, column_name="course_no")
    dept_code = fields.Field(attribute=None, column_name="dept_code")
    college_code = fields.Field(attribute=None, column_name="college_code")
    semester_no = fields.Field(attribute=None, column_name="semester_no")
    academic_year = fields.Field(attribute=None, column_name="academic_year")
    value = fields.Field(
        attribute="value", column_name="grade_code", widget=GradeValueWgt()
    )

    class Meta:
        model = Grade
        import_id_fields = ("student", "section", "grade_code")

    def before_import(self, dataset):
        """Normalize grade file headers."""
        headers = dataset.headers or []
        dataset.headers = [GRADE_HEADER_MAP.get(h, h) for h in headers]
        dataset.headers = [SECTION_HEADER_MAP.get(h, h) for h in headers]

    def dehydrate_std(self, obj):
        student = getattr(obj, "student", None)
        return getattr(student, "student_id", "") if student else ""

    def dehydrate_std_name(self, obj):
        student = getattr(obj, "student", None)
        return getattr(student, "long_name", "") if student else ""

    def dehydrate_curri(self, obj):
        curriculum = getattr(obj.section.curriculum_course, "curriculum", None)
        return getattr(curriculum, "short_name", "") if curriculum else ""

    def dehydrate_crs_no(self, obj):
        course = getattr(obj.section.curriculum_course, "course", None)
        return getattr(course, "number", "") if course else ""

    def dehydrate_dept_code(self, obj):
        course = getattr(obj.section.curriculum_course, "course", None)
        department = getattr(course, "department", None)
        return getattr(department, "code", "") if department else ""

    def dehydrate_college_code(self, obj):
        course = getattr(obj.section.curriculum_course, "course", None)
        department = getattr(course, "department", None)
        college = getattr(department, "college", None)
        return getattr(college, "code", "") if college else ""

    def dehydrate_sem_no(self, obj):
        semester = getattr(obj.section, "semester", None)
        return getattr(semester, "number", "") if semester else ""

    def dehydrate_academic_year(self, obj):
        semester = getattr(obj.section, "semester", None)
        academic_year = getattr(semester, "academic_year", None)
        return getattr(academic_year, "code", "") if academic_year else ""


class RegioResource(resources.ModelResource):
    """Resource for bulk importing :class:Registration rows."""

    class Meta:
        model = Registration
        import_id_fields = ("student", "section")
        fields = (
            "student",
            "section",
            "status",
        )
