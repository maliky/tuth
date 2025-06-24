"""People.Admin.Widgets module.

Usage::

    >>> from app.people.admin.widgets import StaffProfileWidget
    >>> widget = StaffProfileWidget()
    >>> staff = widget.clean("Dr. Jane Doe")
    >>> print(staff.long_name)
"""

from app.people.models.student import Student
from django.contrib.auth import get_user_model
from import_export import widgets

from app.shared.utils import CachedWidgetMixin

from app.people.models.staffs import Faculty, Staff
from app.people.utils import mk_username, split_name
from app.shared.auth.perms import TEST_PW

User = get_user_model()


class StaffProfileWidget(CachedWidgetMixin, widgets.ForeignKeyWidget):

    def __init__(self):
        # Configure the parent widget to operate on the Staff model so
        # that clean returns actual Staff objects using the
        # staff_id field as the lookup key.
        super().__init__(Staff, field="staff_id")

    def clean(self, value, row=None, *args, **kwargs) -> Staff | None:
        """Create or fetch a :class:Staff from a full name.

        The widget splits the display name, creates the corresponding User if
        needed and returns the linked Staff profile so foreign keys can refer to
        it directly.
        """

        if not value:
            return None

        prefix, first, middle, last, suffix = split_name(value)
        username = mk_username(first, last, unique=False)

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
        """For the value (staff) for export."""
        return value.long_name if value else ""  # type: ignore[no-any-return]

    def after_import(self, dataset, result, **kwargs):
        """Clear cached staff objects after each import."""

        super().after_import(dataset, result, **kwargs)


class FacultyWidget(CachedWidgetMixin, widgets.ForeignKeyWidget):
    """Ensure a Faculty entry exists for the given staff name."""

    def __init__(self):
        # field is "id" by default
        super().__init__(Faculty)
        self.staff_w = StaffProfileWidget()

    def clean(self, value: str, row=None, *args, **kwargs) -> Faculty | None:
        """From the faculty name, tries to get a faculty object.

        Create user and staff if necessary.
        """
        if not value:
            return None

        # ? Should I use Peoplerepository.get_or_create_faculty?
        # ... Not obvious as I would need to pass the whole row.
        staff = self.staff_w.clean(value, row, *args, **kwargs)

        if staff is None:
            return None

        key = staff.pk
        if key in self._cache:
            return self._cache[key]

        faculty, _ = Faculty.objects.get_or_create(
            staff_profile=staff,
        )
        self._cache[key] = faculty
        return faculty

    def after_import(self, dataset, result, **kwargs):
        super().after_import(dataset, result, **kwargs)
        self.staff_w.after_import(dataset, result, **kwargs)


class UserWidget(CachedWidgetMixin, widgets.ForeignKeyWidget):
    """Ensure a Faculty entry exists for the given staff name."""

    def __init__(self):
        # field is "id" by default
        super().__init__(Student, field="student_id")

    def clean(self, value: str, row=None, *args, **kwargs) -> Student | None:
        """From the student name (an optionaly an id), gets a Student object.

        Create user and student objects if necessary.
        """
        if not value:
            return None

        std_fullname = (value or "").strip()
        prefix, first, middle, last, suffix = split_name(std_fullname)
        username = mk_username(first, last, unique=True, student_scheme=True)

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

        self._cache[username] = user
        return user

    def after_import(self, dataset, result, **kwargs):
        super().after_import(dataset, result, **kwargs)
