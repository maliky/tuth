"""Import resources for grouped curriculum-course requirements."""

from __future__ import annotations

from typing import Mapping, TypeAlias, cast

from import_export import fields, resources, widgets

from app.academics.ensures import (
    ensure_college,
    ensure_crs,
    ensure_curri,
    ensure_curri_crs,
    ensure_dpt,
)
from app.academics.models.course import Course
from app.academics.models.prerequisite import Prerequisite
from app.academics.models.requirement_group import (
    CurriCrsReqGp,
    CurriCrsReqMember,
    ReqKind,
)
from app.shared.utils import get_in_row, to_int

RowMapT: TypeAlias = Mapping[str, str | None]
REQ_KIND_VALUES = {choice.value for choice in ReqKind}


def _row_text(row: RowMapT | None, key: str) -> str:
    """Return a normalized text value from an import row."""
    return get_in_row(key, row)


def _course_from_row(
    row: RowMapT | None,
    *,
    dept_key: str,
    no_key: str,
    college_key: str,
    title_key: str = "course_title",
) -> Course:
    """Resolve or create a course from scoped row columns."""
    college = ensure_college(
        _row_text(row, college_key) or _row_text(row, "college_code")
    )
    department = ensure_dpt(_row_text(row, dept_key), college)
    return ensure_crs(
        department=department,
        course_no=_row_text(row, no_key),
        title=_row_text(row, title_key) or None,
    )


class RequiredCourseWgt(widgets.ForeignKeyWidget):
    """Resolve the required member course from dedicated row columns."""

    def __init__(self) -> None:
        super().__init__(Course, field="code")

    def clean(
        self, value: object, row: RowMapT | None = None, *args: object, **kwargs: object
    ) -> Course:
        """Return the prerequisite/corequisite course for one member row."""
        return _course_from_row(
            row,
            dept_key="required_course_dept",
            no_key="required_course_no",
            college_key="required_course_college_code",
            title_key="required_course_title",
        )


class RequirementGroupWgt(widgets.ForeignKeyWidget):
    """Resolve the grouped requirement owner for one curriculum-course row."""

    def __init__(self) -> None:
        super().__init__(CurriCrsReqGp, field="label")

    def clean(
        self, value: object, row: RowMapT | None = None, *args: object, **kwargs: object
    ) -> CurriCrsReqGp:
        """Return a deterministic requirement group for the target CurriCrs."""
        row = row or {}
        college = ensure_college(
            _row_text(row, "curriculum_college_code") or _row_text(row, "college_code")
        )
        curriculum = ensure_curri(_row_text(row, "curriculum"), college=college)
        course = _course_from_row(
            row,
            dept_key="course_dept",
            no_key="course_no",
            college_key="course_college_code",
        )
        curriculum_course = ensure_curri_crs(curriculum=curriculum, course=course)
        kind = _row_text(row, "requirement_kind") or ReqKind.PREREQ_ALL
        if kind not in REQ_KIND_VALUES:
            raise ValueError(f"Unsupported requirement_kind: {kind}")
        label = (
            _row_text(row, "requirement_label") or f"source {kind} {course.short_code}"
        )
        order = to_int(_row_text(row, "requirement_order"), default=0)
        group, _ = CurriCrsReqGp.objects.get_or_create(
            curriculum_course=curriculum_course,
            kind=kind,
            label=label[:80],
            defaults={"order": order},
        )
        if group.order != order:
            group.order = order
            group.save(update_fields=["order"])
        return group


class CurriCrsRequirementResource(resources.ModelResource):
    """Import grouped prerequisite/corequisite members for curriculum courses."""

    group_f = fields.Field(
        attribute="group",
        column_name="requirement_label",
        widget=RequirementGroupWgt(),
    )
    required_course_f = fields.Field(
        attribute="required_course",
        column_name="required_course_dept",
        widget=RequiredCourseWgt(),
    )
    member_order_f = fields.Field(
        attribute="order", column_name="member_order", default=0
    )

    def save_instance(self, instance, is_create, row, **kwargs):
        """Persist the member and mirror plain prereq-all rows to legacy edges."""
        super().save_instance(instance, is_create, row, **kwargs)
        if kwargs.get("dry_run", False):
            return
        member = cast(CurriCrsReqMember, instance)
        group = member.group
        if group.kind != ReqKind.PREREQ_ALL:
            return
        curriculum_course = group.curriculum_course
        Prerequisite.objects.get_or_create(
            curriculum=curriculum_course.curriculum,
            course=curriculum_course.course,
            prerequisite_course=member.required_course,
        )

    class Meta:
        model = CurriCrsReqMember
        import_id_fields = ("group_f", "required_course_f")
        fields = ("group_f", "required_course_f", "member_order_f")
        skip_unchanged = True
        report_skipped = True


__all__ = ["CurriCrsRequirementResource"]
