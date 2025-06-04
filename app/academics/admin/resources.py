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


class CourseResource(resources.ModelResource):
    # ── columns coming from the file ───────────────
    name = fields.Field(column_name="name", attribute="name")
    number = fields.Field(column_name="number", attribute="number")
    title = fields.Field(column_name="title", attribute="title")
    credit_hours = fields.Field(column_name="credit_hours", attribute="credit_hours")

    # college is a FK → use the college **code** found in the file
    college = fields.Field(
        column_name="college",  # header in the CSV/XLSX
        attribute="college",  # model field
        widget=widgets.ForeignKeyWidget(  # look-up by…
            College, field="code"  # … College.code
        ),
    )

    # internal column – we *generate* it so import-export can use it as PK
    code = fields.Field(
        column_name="code", attribute="code"
    )  # no header needed in the file

    prerequisites = fields.Field(
        column_name="prerequisites",
        attribute="prerequisites",
        widget=widgets.ManyToManyWidget(Course, field="code", separator=";"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mismatched_rows: list[dict] = []

    # ── hooks ────────────────────────────────────────────────────
    def before_import_row(self, row, **kwargs):
        """Normalize the code fields and flag inconsistent rows."""
        code = row.get("code") or ""
        name, number, _ = expand_course_code(code, row=row)

        if not row.get("name"):
            row["name"] = name
        elif str(row["name"]).strip().upper() != name:
            self._mismatched_rows.append(dict(row))
            row["__skip_row__"] = True
            return

        if not row.get("number"):
            row["number"] = number
        elif str(row["number"]).strip() != number:
            self._mismatched_rows.append(dict(row))
            row["__skip_row__"] = True
            return

        row["code"] = make_course_code(name=row["name"], number=row["number"])

    def skip_row(self, instance, original, row, import_validation_errors=None):
        if row.get("__skip_row__"):
            return True
        return super().skip_row(instance, original, row, import_validation_errors)

    def after_import(self, dataset, result, using_transactions, dry_run=False, **kwargs):
        if dry_run or not self._mismatched_rows:
            return
        request = kwargs.get("request")
        if not request:
            return
        codes = ", ".join(sorted(r.get("code", "") for r in self._mismatched_rows))
        messages.warning(
            request,
            (f"{len(self._mismatched_rows)} course rows skipped: {codes}."),
        )

    class Meta:
        model = Course
        import_id_fields = ("name", "number", "college")
        fields = (
            "name",
            "number",
            "title",
            "credit_hours",
            "college",
            "prerequisites",
            "code",  # include it so the generated value reaches save()
        )
        skip_unchanged = True
        report_skipped = True


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
