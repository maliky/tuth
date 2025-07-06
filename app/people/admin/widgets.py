"""People.Admin.Widgets module.

Usage::

    >>> from app.people.admin.widgets import StaffProfileWidget
    >>> widget = StaffProfileWidget()
    >>> staff = widget.clean("Dr. Jane Doe")
    >>> print(staff.long_name)
"""

from django.contrib.auth.models import User
from import_export import widgets

from app.people.models.staffs import Faculty, Staff
from app.people.utils import mk_username, split_name
from app.shared.auth.perms import TEST_PW


class StaffProfileWidget(widgets.ForeignKeyWidget):

    def __init__(self):
        super().__init__(Staff, field="staff_id")

    def clean(self, value, row=None, *args, **kwargs) -> Staff:
        """Create or fetch a Staff from a name.

        The widget splits the name, creates and the corresponding User if
        needed.  It returns or creates the linked Staff profile.

        If no value, create a new unique staff.
        """

        if not value:
            return Staff.get_unique_default()

        prefix, first, middle, last, suffix = split_name(value)
        username = mk_username(first, last, prefix_len=2)

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
        return staff

    def render(self, value, obj=None) -> str:
        """For the value (staff) for export."""
        return value.long_name if value else ""  # type: ignore[no-any-return]

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        if kwargs.get("dry_run", False):
            self._cache.clear()


class FacultyWidget(widgets.ForeignKeyWidget):
    """Ensure a Faculty entry exists for the given staff name."""

    def __init__(self):
        # field is "id" by default
        super().__init__(Faculty)

    def clean(self, value: str, row=None, *args, **kwargs) -> Faculty:
        """From the faculty name, tries to get a faculty object.

        Create user and staff if necessary.
        if value is '<unique>' create a default unique faculty
        """
        if not value:
            return Faculty.get_unique_default()

        # ? Should I use Peoplerepository.get_or_create_faculty?
        # ... Not obvious as I would need to pass the whole row.
        staff = StaffProfileWidget().clean(value, row, *args, **kwargs)

        faculty, _ = Faculty.objects.get_or_create(
            staff_profile=staff,
        )
        return faculty


class StudentUserWidget(widgets.ForeignKeyWidget):
    """Ensure a Student User exists."""

    def __init__(self):
        # field is "id" by default
        super().__init__(User)
        self._cache: dict[str, str] = dict()
        self._exclude = set()

    def clean(self, value: str, row=None, *args, **kwargs) -> User | None:
        """From the student name (an optionaly an id), gets a Student object.

        Create user and student objects if necessary.
        Use the extrat colum student_id to desambiguate sames names
        and create uniq username.
        """

        if not value:
            return None

        std_fullname = (value or "").strip()
        prefix, first, middle, last, suffix = split_name(std_fullname)

        assert "student_id" in row
        stdid = row.get("student_id")
        username = self._cache.get(
            stdid, mk_username(first, last, middle, exclude=self._exclude)
        )
        self._cache[stdid] = username
        self._exclude |= {username}

        user, _ = User.objects.get_or_create(
            username=username,
            defaults={
                "first_name": first.capitalize(),
                "last_name": last.capitalize(),
                "password": TEST_PW,
            },
        )
        return user

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        self._exclude = set()
        self.cache = dict()        
