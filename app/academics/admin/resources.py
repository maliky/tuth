"""Resources module."""

from app.academics.choices import CREDIT_NUMBER
from django.contrib import messages
from import_export import fields, resources

from app.academics.admin.widgets import (
    CollegeWidget,
    CourseManyWidget,
    CourseWidget,
    CurriculumWidget,
    DepartmentWidget,
)

from app.academics.models.college import College
from app.academics.models.course import Course
from app.academics.models.curriculum import Curriculum
from app.academics.models.program import Program
from app.academics.models.prerequisite import Prerequisite
from app.academics.models.department import Department


class CurriculumResource(resources.ModelResource):
    """Columns expected in the CSV: short_name, title, college, list_courses."""

    def __init__(self, *args, **kwargs):
        """For keeping track of what is been added or replaced."""
        super().__init__(*args, **kwargs)
        self._created: set[str] = set()
        self._merged: set[str] = set()
        self._replaced: set[str] = set()
        self._new_colleges: set[str] = set()
        self.fields["college"].widget._resource = self

    def _action(self) -> str:
        """Merge (default) or 'replace'  — read once from the import form."""
        value = (self._kwargs or {}).get("action", "merge")
        return str(value).lower()  # str to garantee return type for mypy

    college_f = fields.Field(
        column_name="college_code",
        attribute="college",
        widget=CollegeWidget(),
    )
    list_courses_f = fields.Field(
        column_name="list_courses",
        attribute="courses",
        widget=CourseManyWidget(),
    )
    short_name_f = fields.Field(attribute="short_name", column_name="curriculum")

    def save_instance(self, instance, is_create, row, **kwargs):
        """Handle merge/replace logic for curriculum imports.

        Updated signature to match django-import-export 4.x which
        provides is_create and row parameters along with
        keyword-only dry_run.
        """
        exists = instance.pk is not None
        super().save_instance(instance, is_create, row, **kwargs)

        if kwargs.get("dry_run", False):
            return  # nothing else to do

        short_name = instance.short_name
        if not exists:
            self._created.add(short_name)
        elif self._action() == "replace":
            instance.courses.clear()
            self._replaced.add(short_name)
        else:
            self._merged.add(short_name)

    def after_import(self, dataset, result, **kwargs):
        """Post-import summary."""
        super().after_import(dataset, result, **kwargs)

        if kwargs.get("dry_run", False):
            return

        request = kwargs.get("request")
        if not request:
            return

        parts: list[str] = []
        if self._created:
            parts.append(f"curricula {', '.join(sorted(self._created))} created")
        if self._merged:
            parts.append(f"curricula {', '.join(sorted(self._merged))} updated")
        if self._replaced:
            parts.append(f"curricula {', '.join(sorted(self._replaced))} replaced")

        if parts:
            msg = " · ".join(parts)
            if self._new_colleges:
                msg += f" · colleges {', '.join(sorted(self._new_colleges))} created"
            messages.success(request, msg.capitalize() + ".")

    class Meta:
        model = Curriculum
        import_id_fields = ("short_name_f",)
        fields = (
            "short_name_f",
            "title",
            "college_f",
            "list_courses_f",
        )
        skip_unchanged = True
        report_skipped = True


class CourseResource(resources.ModelResource):
    """Import / export definition for Course rows.

    Row should come from a CSV file with: course_dept, course_no and college_code columns.

    Additional: course_title, prerequisites
    """

    number_f = fields.Field(attribute="number", column_name="course_no")  # 121
    title_f = fields.Field(attribute="title", column_name="course_title")

    department_f = fields.Field(
        attribute="department", column_name="course_dept", widget=DepartmentWidget()
    )
    prerequisite_f = fields.Field(
        attribute="prerequisites",
        column_name="prerequisites",
        widget=CourseManyWidget(),
    )

    def __init__(self, *args, **kwargs):
        """Constructor – track rows skipped by validation logic."""
        super().__init__(*args, **kwargs)
        self._mismatched_rows: list[dict] = []  # for admin feedback

    class Meta:
        model = Course
        # Uniqueness criterion for updates
        import_id_fields = ("number_f", "department_f")
        # Exposed / accepted columns
        fields = (
            "number_f",
            "department_f",
            "title_f",
            "prerequisite_f",
        )
        skip_unchanged = True  # do not rewrite identical rows
        report_skipped = False  # include skipped-row info in the Result


class PrerequisiteResource(resources.ModelResource):
    curriculum_f = fields.Field(
        column_name="curriculum",
        attribute="curriculum",
        widget=CurriculumWidget(),
    )
    course_f = fields.Field(
        column_name="course_dept", attribute="course", widget=CourseWidget()
    )
    prerequisite_course_f = fields.Field(
        column_name="prerequisite",
        attribute="prerequisite_course",
        widget=CourseWidget(),
    )

    class Meta:
        model = Prerequisite
        import_id_fields = (
            "curriculum_f",
            "course_f",
            "prerequisite_course_f",
        )
        fields = ("curriculum_f", "course_f", "prerequisite_course_f")


class CollegeResource(resources.ModelResource):
    """Simple import-export resource for College."""

    college_f = fields.Field(
        attribute="code", column_name="college_code", widget=CollegeWidget()
    )

    class Meta:
        model = College
        import_id_fields = ("college_f",)
        fields = (
            "college_f",
            "long_name",
        )


class ProgramResource(resources.ModelResource):
    """Import a program  curriculum name and course no and dept."""

    curriculum_f = fields.Field(
        attribute="curriculum",
        column_name="curriculum",
        widget=CurriculumWidget(),
    )
    # requires course_no columns too
    course_f = fields.Field(
        attribute="course",
        column_name="course_dept",
        widget=CourseWidget(),
    )
    credit_hours_f = fields.Field(
        attribute="credit_hours", column_name="credit_hours", default=CREDIT_NUMBER.THREE
    )

    class Meta:
        model = Program
        import_id_fields = (
            "curriculum_f",
            "course_f",
        )
        fields = (
            "curriculum_f",
            "course_f",
            "credit_hours_f",
        )
        list_filter = ("curriculum_college", "curriculum")
        skip_unchanged = True
        report_skipped = True


class DepartmentResource(resources.ModelResource):
    """Resource for Department."""

    dept_f = fields.Field(
        attribute="short_name", column_name="course_dept", widget=DepartmentWidget()
    )
    college_f = fields.Field(
        attribute="college", column_name="college_code", widget=CollegeWidget()
    )

    class Meta:
        model = Department
        import_id_fields = ("dept_f", "college_f")
        fields = (
            "dept_f",
            "college_f",
        )
