"""registry.admin.widgets module."""

from import_export import widgets

from app.registry.models.grade import GradeValue


class GradeValueWidget(widgets.ForeignKeyWidget):
    """Look up or create a GradeValue from a CSV grade code."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(GradeValue, field="code")

    def clean(self, value, row=None, *args, **kwargs) -> GradeValue | None:
        """Return a GradeValue matching the provided letter Code."""
        if not value:
            return None

        code = str(value).strip().lower()
        # ! code should be a gradeChoice
        grade_value, _ = GradeValue.objects.get_or_create(code=code)
        return grade_value
