"""Course import-export resource."""

from __future__ import annotations

from typing import TypeAlias

from import_export import fields, resources

from app.academics.admin.widgets import CrsManyWgt, DptWgt
from app.academics.models.course import Course
from app.shared.importing.rows import require_course_identity

SkippedCourseRowsT: TypeAlias = list[tuple[int, dict, str]]


class CrsResource(resources.ModelResource):
    """Import/export definition for Course rows."""

    number_f = fields.Field(attribute="number", column_name="course_no")
    title_f = fields.Field(attribute="title", column_name="course_title")
    description_f = fields.Field(attribute="description", column_name="description")
    department_f = fields.Field(
        attribute="department", column_name="course_dept", widget=DptWgt()
    )
    prerequisite_f = fields.Field(
        attribute="prerequisites",
        column_name="prerequisites",
        widget=CrsManyWgt(),
    )

    def __init__(self, *args, **kwargs):
        """Track malformed rows skipped by command-line imports."""
        super().__init__(*args, **kwargs)
        self._skipped_invalid_rows: SkippedCourseRowsT = []

    def before_import_row(self, row, **kwargs):
        """Normalize course identity columns before model resolution."""
        self._normalize_course_identity(row)
        return super().before_import_row(row, **kwargs)

    def should_skip_row(self, row, row_number: int, **kwargs) -> bool:
        """Skip malformed course identities before database writes."""
        try:
            self._normalize_course_identity(row)
        except ValueError as exc:
            self._skipped_invalid_rows.append((row_number, dict(row), str(exc)))
            return True
        return False

    def post_import_report(self, command) -> None:
        """Report malformed course rows skipped before database writes."""
        for row_number, row, reason in self._skipped_invalid_rows[:5]:
            command.stdout.write(
                command.style.WARNING(
                    f"Skipped Course row {row_number}: {reason}; data: {row}"
                )
            )
        if self._skipped_invalid_rows:
            command.stdout.write(
                command.style.WARNING(
                    f"Skipped {len(self._skipped_invalid_rows)} malformed Course rows."
                )
            )

    def _normalize_course_identity(self, row) -> None:
        """Mutate a row so course_dept/course_no use the shared parser."""
        dept_code, course_no = require_course_identity(row)
        row["course_dept"] = dept_code
        row["course_no"] = course_no
        if "dept_code" in row:
            row["dept_code"] = dept_code

    class Meta:
        model = Course
        import_id_fields = ("number_f", "department_f")
        fields = (
            "number_f",
            "department_f",
            "title_f",
            "description_f",
            "prerequisite_f",
        )
        skip_unchanged = True
        report_skipped = False
