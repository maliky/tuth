"""Resources module."""

from django.contrib import messages
from import_export import fields, resources, widgets

from app.academics.admin.widgets import (
    CollegeWgt,
    CreditHourWgt,
    CrsManyWgt,
    CrsWgt,
    CurriWgt,
    DptWgt,
)
from app.academics.admin.course_resource import CrsResource

from app.academics.models.college import College
from app.academics.models.curriculum import Curriculum, CurriStatus
from app.academics.models.curriculum_course import CurriCrs
from app.academics.models.prerequisite import Prerequisite
from app.academics.models.department import Department


class CurriStatusWgt(widgets.ForeignKeyWidget):
    """Resolve or create curriculum status rows during curriculum imports."""

    def __init__(self):
        super().__init__(CurriStatus, field="code")

    def clean(self, value, row=None, *args, **kwargs) -> CurriStatus:
        """Return a curriculum status, defaulting to pending."""
        code = str(value or "pending").strip() or "pending"
        status, _ = CurriStatus.objects.get_or_create(
            code=code,
            defaults={"label": code.replace("_", " ").title()},
        )
        return status


class CurriResource(resources.ModelResource):
    """Columns expected in the CSV: short_name, title, college, list_courses."""

    def __init__(self, *args, **kwargs):
        """For keeping track of what is been added or replaced."""
        self._import_action = str(kwargs.pop("action", "merge")).lower()
        super().__init__(*args, **kwargs)
        self._created: set[str] = set()
        self._merged: set[str] = set()
        self._replaced: set[str] = set()
        self._new_colleges: set[str] = set()
        if "college_f" in self.fields:
            self.fields["college_f"].widget._resource = self

    def _action(self) -> str:
        """Merge (default) or 'replace'  — read once from the import form."""
        return self._import_action

    college_f = fields.Field(
        column_name="college_code",
        attribute="college",
        widget=CollegeWgt(),
    )
    list_courses_f = fields.Field(
        column_name="list_courses",
        attribute="courses",
        widget=CrsManyWgt(),
    )
    short_name_f = fields.Field(attribute="short_name", column_name="curriculum")
    status_f = fields.Field(
        column_name="status",
        attribute="status",
        widget=CurriStatusWgt(),
    )
    is_active_f = fields.Field(
        column_name="is_active",
        attribute="is_active",
        widget=widgets.BooleanWidget(),
    )

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
        import_id_fields = ("short_name_f", "college_f")
        fields = (
            "short_name_f",
            "long_name",
            "college_f",
            "status_f",
            "is_active_f",
            "list_courses_f",
        )
        skip_unchanged = True
        report_skipped = True


class PrerequisiteResource(resources.ModelResource):
    curriculum_f = fields.Field(
        column_name="curriculum",
        attribute="curriculum",
        widget=CurriWgt(),
    )
    course_f = fields.Field(
        column_name="course_dept", attribute="course", widget=CrsWgt()
    )
    prerequisite_course_f = fields.Field(
        column_name="prerequisite",
        attribute="prerequisite_course",
        widget=CrsWgt(),
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
        attribute="code", column_name="college_code", widget=CollegeWgt()
    )

    class Meta:
        model = College
        import_id_fields = ("college_f",)
        fields = (
            "college_f",
            "long_name",
        )


class CurriCrsResource(resources.ModelResource):
    """Import a curriculum_course  curriculum name and course no and dept."""

    curriculum_f = fields.Field(
        attribute="curriculum",
        column_name="curriculum",
        widget=CurriWgt(),
    )
    # requires course_no columns too
    course_f = fields.Field(
        attribute="course",
        column_name="course_dept",
        widget=CrsWgt(),
    )
    credit_hours_f = fields.Field(
        attribute="credit_hours",
        column_name="credit_hours",
        default=3,
        widget=CreditHourWgt(),
    )
    year_number_f = fields.Field(
        attribute="year_number", column_name="year_number", default=99
    )
    semester_number_f = fields.Field(
        attribute="semester_number", column_name="semester_number", default=0
    )
    level_number_f = fields.Field(
        attribute="level_number", column_name="level_number", default=99
    )
    required_group_number_f = fields.Field(
        attribute="required_group_number",
        column_name="required_group_number",
        default=0,
    )
    min_validated_credits_f = fields.Field(
        attribute="min_validated_credits",
        column_name="min_validated_credits",
        default=0,
    )

    class Meta:
        model = CurriCrs
        import_id_fields = (
            "curriculum_f",
            "course_f",
        )
        fields = (
            "curriculum_f",
            "course_f",
            "credit_hours_f",
            "year_number_f",
            "semester_number_f",
            "level_number_f",
            "required_group_number_f",
            "min_validated_credits_f",
        )
        list_filter = ("curriculum_college", "curriculum")
        skip_unchanged = True
        report_skipped = True


class DptResource(resources.ModelResource):
    """Resource for Department."""

    class Meta:
        model = Department
        import_id_fields = "department_shortname"
        # should I have __ instead of _ ?
        fields = (
            "college_code",
            "course_dept",
            "department_shortname",
            "long_name",
        )
