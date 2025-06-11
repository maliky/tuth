"""Resources module."""

from django.contrib import messages
from import_export import fields, resources, widgets

from app.academics.admin.widgets import (
    CollegeWidget,
    CourseManyWidget,
    CourseWidget,
    CurriculumWidget,
)
from app.academics.models import (
    College,
    Course,
    Curriculum,
    CurriculumCourse,
    Prerequisite,
)


class CurriculumResource(resources.ModelResource):
    """
    Columns expected in the CSV  (case-sensitive):
        short_name, title, college, list_courses
    """

    # -------- bookkeeping ---------------------------------------------------
    def __init__(self, *args, **kwargs):
        # for keeping track of what is been added or replaced
        super().__init__(*args, **kwargs)
        self._created: set[str] = set()
        self._merged: set[str] = set()
        self._replaced: set[str] = set()
        self._new_colleges: set[str] = set()
        self.fields["college"].widget._resource = self

    # ------------------------------------------------------------------ helpers
    def _action(self) -> str:
        """
        'merge' (default) or 'replace'  — read once from the import form.
        """
        value = (self._kwargs or {}).get("action", "merge")
        return str(value).lower()  # str to garantee return type for mypy

    # ----- FKs ---------------------------------------------------------------
    college = fields.Field(
        column_name="college_code",
        attribute="college",
        widget=widgets.ForeignKeyWidget(College, field="code"),
    )

    # ----- synthetic M2M list -----------------------------------------------
    list_courses = fields.Field(
        column_name="list_courses",
        attribute="courses",
        widget=CourseManyWidget(),  # ⬆ defined in step 1
    )

    # ----- niceties ----------------------------------------------------------
    def before_import_row(self, row, **kwargs):
        # default long_name -> short_name
        if not row.get("long_name"):
            row["long_name"] = row["short_name"]

    # ----- merge / replace logic --------------------------------------------
    def save_instance(self, instance, is_create, row, **kwargs):
        """Handle merge/replace logic for curriculum imports.

        Updated signature to match ``django-import-export`` 4.x which
        provides ``is_create`` and ``row`` parameters along with
        keyword-only ``dry_run``.
        """
        dry_run = kwargs.get("dry_run", False)
        exists = instance.pk is not None
        super().save_instance(instance, is_create, row, **kwargs)

        if dry_run:
            return  # nothing else to do

        sn = instance.short_name
        if not exists:
            self._created.add(sn)
        elif self._action() == "replace":
            instance.courses.clear()
            self._replaced.add(sn)
        else:
            self._merged.add(sn)

    def after_save_instance(self, instance, row, **kwargs):
        """Post-save hook after M2M cleanup."""
        return super().after_save_instance(instance, row, **kwargs)

    def after_import(self, dataset, result, **kwargs):
        """Post-import summary."""
        super().after_import(dataset, result, **kwargs)
        dry_run = kwargs.get("dry_run", False)
        if dry_run:  # nothing permanent happened
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

    # ----- Meta --------------------------------------------------------------
    class Meta:
        model = Curriculum
        import_id_fields = ("short_name",)
        fields = (
            "short_name",
            "title",
            "college",
            "list_courses",
        )
        skip_unchanged = True
        report_skipped = True


class CourseResource(resources.ModelResource):
    """
    Import / export definition for Course rows coming from the *cleaned_tscc.csv*
    file (or any file that has **separate** course_name / course_no columns).

    Columns expected in the CSV (case-sensitive):
        course_name, course_no, course_title, credit_hours, college_code, prerequisites
    """

    # ─── columns that map 1-to-1 onto Course fields ──────────────────────────

    name = fields.Field(column_name="course_name", attribute="name")  # AGR
    number = fields.Field(column_name="course_no", attribute="number")  # 121
    title = fields.Field(column_name="course_title", attribute="title")
    # credit_hours = fields.Field(column_name="credit_hours", attribute="credit_hours")

    # ─── college FK – lookup by code via CollegeWidget ───────────────────────
    college = fields.Field(
        column_name="college_code", attribute="college", widget=CollegeWidget()
    )

    # ─── many-to-many prerequisites – semicolon-separated list of codes ──────
    prerequisites = fields.Field(
        column_name="prerequisites",
        attribute="prerequisites",
        widget=widgets.ManyToManyWidget(Course, field="code", separator=";"),
    )

    # ─── constructor – track rows skipped by validation logic ────────────────
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mismatched_rows: list[dict] = []  # for admin feedback

    class Meta:
        model = Course
        # Uniqueness criterion for updates
        import_id_fields = ("name", "number", "college")
        # Exposed / accepted columns
        fields = (
            "name",
            "number",
            "title",
            "credit_hours",
            "college",
            "prerequisites",
        )
        skip_unchanged = True  # do not rewrite identical rows
        report_skipped = True  # include skipped-row info in the Result


class PrerequisiteResource(resources.ModelResource):
    curriculum = fields.Field(
        column_name="curriculum",
        attribute="curriculum",
        widget=CurriculumWidget(),
    )
    course = fields.Field(
        column_name="course_code", attribute="course", widget=CourseWidget()
    )
    prerequisite_course = fields.Field(
        column_name="prerequisite", attribute="prerequisite_course", widget=CourseWidget()
    )

    class Meta:
        model = Prerequisite
        import_id_fields = ("curriculum", "course", "prerequisite_course")
        fields = ("curriculum", "course", "prerequisite_course")


class CollegeResource(resources.ModelResource):
    """Simple import-export resource for :class:`~app.academics.models.College`."""

    class Meta:
        model = College
        import_id_fields = ("code",)
        fields = (
            "code",
            "long_name",
        )


class CurriculumCourseResource(resources.ModelResource):
    """Import curriculum-course rows with a curriculum name and course code."""

    curriculum = fields.Field(
        column_name="curriculum",
        attribute="curriculum",
        widget=CurriculumWidget(),
    )
    course = fields.Field(
        column_name="course_name",
        attribute="course",
        widget=CourseWidget(),
    )

    class Meta:
        model = CurriculumCourse
        import_id_fields = (
            "curriculum",
            "course",
        )
        fields = (
            "curriculum",
            "course",
            "credit_hours",
        )
        skip_unchanged = True
        report_skipped = True
