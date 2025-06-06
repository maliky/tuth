"""Resources module."""

from django.contrib import messages
from import_export import fields, resources, widgets

from app.academics.admin.widgets import (
    CollegeWidget,
    CourseManyWidget,
    CourseCodeWidget,
    CurriculumWidget,
)
from app.academics.models import (
    College,
    Course,
    Curriculum,
    CurriculumCourse,
    Prerequisite,
)
from app.shared.utils import expand_course_code, make_course_code


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
        column_name="college",
        attribute="college",
        widget=CollegeWidget(model=College, field="code"),  # auto-creates + logs
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


# app/academics/admin/resources.py  – excerpt
from import_export import resources, fields, widgets
from django.contrib import messages

from app.academics.models import Course, College
from app.academics.admin.widgets import CollegeWidget
from app.shared.utils import make_course_code


class CourseResource(resources.ModelResource):
    """
    Import / export definition for Course rows coming from the *cleaned_tscc.csv*
    file (or any file that has **separate** course_code / course_no columns).

    Columns expected in the CSV (case-sensitive):
        course_code, course_no, title, credit, college, prerequisites
    """

    # ─── columns that map 1-to-1 onto Course fields ──────────────────────────
    name = fields.Field(column_name="course_code", attribute="name")  # AGR
    number = fields.Field(column_name="course_no", attribute="number")  # 121
    title = fields.Field(column_name="title", attribute="title")
    credit_hours = fields.Field(column_name="credit", attribute="credit_hours")

    # ─── college FK – lookup by code via CollegeWidget ───────────────────────
    college = fields.Field(
        column_name="college",
        attribute="college",
        widget=CollegeWidget(College, field="code"),  # "CAFS" → <College id=…>
    )

    # ─── internal “code” column – generated on the fly (AGR121) ──────────────
    code = fields.Field(column_name="code", attribute="code")

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

    # ── import-export hooks ──────────────────────────────────────────────────
    def before_import_row(self, row: dict, **kwargs) -> None:
        """
        Build the compact ``code`` (e.g. AGR121) so import-export can
        use it as the primary key for lookups / updates.
        """
        row["code"] = make_course_code(row["course_code"], row["course_no"])

        # If you need to skip rows with missing dept/num, mark them:
        if not row["course_code"] or not row["course_no"]:
            row["__skip_row__"] = True
            self._mismatched_rows.append(row)

    def skip_row(  # noqa: D401  (import-export API)
        self,
        instance,
        original,
        row,
        import_validation_errors=None,
    ) -> bool:
        """Import-export calls this to decide whether to skip the row."""
        if row.get("__skip_row__"):
            return True
        return super().skip_row(instance, original, row, import_validation_errors)

    def after_import(
        self,
        dataset,
        result,
        using_transactions,
        dry_run: bool = False,
        **kwargs,
    ) -> None:
        """
        Once the import finishes, flash one admin message if we skipped rows due
        to missing / mismatched data.
        """
        if dry_run or not self._mismatched_rows:
            return

        request = kwargs.get("request")  # present only in admin import
        if not request:
            return

        codes = ", ".join(sorted(r.get("code", "") for r in self._mismatched_rows))
        messages.warning(
            request,
            f"{len(self._mismatched_rows)} course rows skipped: {codes}.",
        )

    # ── meta options ─────────────────────────────────────────────────────────
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
            "code",
        )
        skip_unchanged = True  # do not rewrite identical rows
        report_skipped = True  # include skipped-row info in the Result


class PrerequisiteResource(resources.ModelResource):
    curriculum = fields.Field(
        column_name="curriculum",
        attribute="curriculum",
        widget=widgets.ForeignKeyWidget(Curriculum, field="short_name"),
    )
    course = fields.Field(
        column_name="course",
        attribute="course",
        widget=widgets.ForeignKeyWidget(Course, field="code"),
    )
    prerequisite_course = fields.Field(
        column_name="prerequisite",
        attribute="prerequisite_course",
        widget=widgets.ForeignKeyWidget(Course, field="code"),
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
            "fullname",
        )


class CurriculumCourseResource(resources.ModelResource):
    """Import curriculum-course rows with a curriculum name and course code."""

    curriculum = fields.Field(
        column_name="curriculum_name",
        attribute="curriculum",
        widget=CurriculumWidget(model=Curriculum, field="short_name"),
    )
    college = fields.Field(column_name="college")
    course = fields.Field(
        column_name="course",
        attribute="course",
        widget=CourseCodeWidget(model=Course, field="code"),
    )

    class Meta:
        model = CurriculumCourse
        import_id_fields = ("curriculum", "course")
        fields = (
            "curriculum",
            "college",
            "course",
        )
        skip_unchanged = True
        report_skipped = True

    def dehydrate_college(self, obj):
        return obj.curriculum.college.code
