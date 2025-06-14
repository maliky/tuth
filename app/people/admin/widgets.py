"""People.Admin.Widgets module."""

from app.academics.admin.widgets import CollegeWidget
from django.contrib.auth import get_user_model
from import_export import widgets

from app.people.models.staffs import Faculty, Staff
from app.people.utils import mk_username, split_name
from app.shared.constants import TEST_PW

User = get_user_model()


class StaffProfileWidget(widgets.ForeignKeyWidget):
    """
    “faculty”  ➜  User  ➜  Staff

    • expects the column value to be the full display name.
    • returns the *Staff* (not the User!) so foreign-keys can point to it.
    """

    def __init__(self):
        # > explain this,  Does it means to initiate a Staff instance ,
        super().__init__(Staff, field="staff_id")
        self._cache: dict[str, Staff] = {}

    def clean(self, value, row=None, *args, **kwargs) -> Staff | None:
        if not value:
            return None

        prefix, first, middle, last, suffix = split_name(value)
        username = mk_username(first, last, unique=True)

        if username in self._cache:
            return self._cache[username]

        user, _ = User.objects.get_or_create(
            username=username,
            defaults={
                "first_name": first.capitalize(),
                "last_name": last.capitalize(),
                "password": TEST_PW,
            },
        )

        staff, _ = Staff.objects.get_or_create(
            user=user,
            defaults={
                "name_prefix": prefix,
                "middle_name": middle,
                "name_suffix": suffix,
            },
        )
        self._cache[username] = staff
        return staff

    def render(self, value, obj=None) -> str:
        return value.long_name if value else ""  # type: ignore[no-any-return]

    def after_import(self, dataset, result, **kwargs):
        if kwargs.get("dry_run", False):
            self._cache.clear()


class FacultyWidget(widgets.ForeignKeyWidget):
    """
    Builds on StaffWidget: first get the Staff, then ensure a Faculty row exists.
    """

    def __init__(self):
        # field is "id" by default
        super().__init__(Faculty)

    def clean(self, value: str, row=None, *args, **kwargs) -> Faculty | None:
        if not value:
            return None

        staff = StaffProfileWidget().clean(value, row, *args, **kwargs)

        if staff is None:
            return None
        # pick the college code from the row (or a default)

        code = (row or {}).get("college_code", "COAS").strip().upper()
        college = CollegeWidget().clean(code, row)

        faculty, _ = Faculty.objects.get_or_create(
            staff_profile=staff,
            defaults={"college": college},
        )
        return faculty
