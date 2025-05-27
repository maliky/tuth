from django.contrib import messages
from import_export import resources, fields, widgets
from app.academics.admin.widgets import CollegeWidget, CourseManyWidget
from app.academics.models import (
    Curriculum,
    Course,
    Prerequisite,
    College,
)
from app.shared.utils import make_course_code


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
    def save_instance(self, instance, using_transactions=True, dry_run=False):
        """
        Merge vs Replace:
          – If Curriculum exists AND already has courses,
            look for `action` whose value can be 'merge' or 'replace'.
          – Absent / invalid => default to *merge*.
        """
        exists = instance.pk is not None
        super().save_instance(instance, using_transactions, dry_run)

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

    def after_save_instance(self, instance, using_transactions=True, dry_run=False):
        """
        Hook happens *after* Many-to-Many relations have been cleaned by the
        widget.  We do nothing special here – creation was already handled
        by CourseManyWidget.
        """
        return super().after_save_instance(instance, using_transactions, dry_run)

    def after_import(self, dataset, result, using_transactions, dry_run=False, **kwargs):
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
    name = fields.Field(column_name="name")
    number = fields.Field(column_name="number")
    title = fields.Field(column_name="title")
    credit_hours = fields.Field(column_name="credit_hours")

    # college is a FK → use the college **code** found in the file
    college = fields.Field(
        column_name="college",  # header in the CSV/XLSX
        attribute="college",  # model field
        widget=widgets.ForeignKeyWidget(  # look-up by…
            College, field="code"  # … College.code
        ),
    )

    # internal column – we *generate* it so import-export can use it as PK
    code = fields.Field(column_name="code")  # no header needed in the file

    prerequisites = fields.Field(
        column_name="prerequisites",
        attribute="prerequisites",
        widget=widgets.ManyToManyWidget(Course, field="code", separator=";"),
    )

    # ── hooks ────────────────────────────────────────────────────
    def before_import_row(self, row, **kwargs):
        """
        Build the missing `code` on the fly so that
        import-export can identify (or create) the row.
        """
        if not row.get("code"):
            # penser à avoir une fonction dans utils qui génère le code du course
            # permettrat de changer cela consitently accross code base.
            row["code"] = make_course_code(row["name"], row["number"])

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
