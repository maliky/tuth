"""People.Admin.Widgets module.

Usage::

    >>> from app.people.admin.widgets import StaffProfileWidget
    >>> widget = StaffProfileWidget()
    >>> staff = widget.clean("Dr. Jane Doe")
    >>> print(staff.long_name)
"""

from django.contrib.auth import get_user_model
from import_export import widgets

from app.people.models.staffs import Faculty, Staff
from app.people.utils import mk_username, split_name
from app.shared.auth.perms import TEST_PW

TEST_PW
User = get_user_model()


class StaffProfileWidget(widgets.ForeignKeyWidget):
    """Create or fetch a :class:`Staff` from a full name.

    The widget splits the display name, creates the corresponding ``User`` if
    needed and returns the linked ``Staff`` profile so foreign keys can refer to
    it directly.
    """

    def __init__(self):
        # Configure the parent widget to operate on the Staff model so
        # that ``clean`` returns actual ``Staff`` objects using the
        # ``staff_id`` field as the lookup key.
        super().__init__(Staff, field="staff_id")
        # self._cache: dict[str, Staff] = {}

    def clean(self, value, row=None, *args, **kwargs) -> Staff | None:
        if not value:
            return None

        prefix, first, middle, last, suffix = split_name(value)
        username = mk_username(first, last, unique=False)

        # if username in self._cache:
        #     return self._cache[username]

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
        # self._cache[username] = staff
        return staff

    def render(self, value, obj=None) -> str:
        return value.long_name if value else ""  # type: ignore[no-any-return]

    def after_import(self, dataset, result, **kwargs):
        if kwargs.get("dry_run", False):
            self._cache.clear()


class FacultyWidget(widgets.ForeignKeyWidget):
    """Ensure a :class:`Faculty` entry exists for the given staff name."""

    def __init__(self):
        # field is "id" by default
        super().__init__(Faculty)

    def clean(self, value: str, row=None, *args, **kwargs) -> Faculty | None:
        if not value:
            return None

        # ? Should I use Peoplerepository.get_or_create_faculty?
        staff = StaffProfileWidget().clean(value, row, *args, **kwargs)

        if staff is None:
            return None


        faculty, _ = Faculty.objects.get_or_create(
            staff_profile=staff,
        )
        return faculty
