from import_export import resources, fields, widgets
from app.academics.models import (
    Curriculum,
    Course,
    CurriculumCourse,
    Prerequisite,
    College,
)
from app.shared.utils import make_course_code


class CurriculumCourseResource(resources.ModelResource):
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

    class Meta:
        model = CurriculumCourse
        import_id_fields = ("curriculum", "course")
        fields = ("curriculum", "course")


class CurriculumResource(resources.ModelResource):
    class Meta:
        model = Curriculum
        fields = (
            "title",
            "short_name",
            "creation_date",
            "college__code",
            "is_active",
        )


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
