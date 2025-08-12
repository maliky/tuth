"""People.Admin.Widgets module.

Usage::

    >>> from app.people.admin.widgets import StaffProfileWidget
    >>> widget = StaffProfileWidget()
    >>> staff = widget.clean("Dr. Jane Doe")
    >>> print(staff.long_name)
"""

from typing import cast
from app.people.models.student import Student
from django.contrib.auth.models import User
from import_export import widgets

from app.people.models.staffs import Staff
from app.people.models.faculty import Faculty
from app.people.utils import mk_username, split_name
from app.shared.auth.perms import TEST_PW


class StaffProfileWidget(widgets.ForeignKeyWidget):

    def __init__(self):
        self._cache_staff: dict[str, tuple[Staff, bool]] = dict()
        super().__init__(Staff, field="staff_id")

    def clean(self, value, row=None, *args, **kwargs) -> Staff:
        """Create or fetch a Staff from a name.

        The widget splits the name, creates and the corresponding User if
        needed.  It returns or creates the linked Staff profile.
        """

        if not value:
            return Staff.get_unique_default()

        prefix, first, middle, last, suffix = split_name(value)
        username = mk_username(first, last, prefix_len=2)

        staff, _ = self._cache_staff.setdefault(
            username,
            Staff.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first.capitalize(),
                    "last_name": last.capitalize(),
                    "password": TEST_PW,
                    "name_prefix": prefix,
                    "middle_name": middle,
                    "name_suffix": suffix,
                },
            ),
        )

        return staff

    def render(self, value, obj=None) -> str:
        """For the value (staff) for export."""
        return value.long_name if value else ""  # type: ignore[no-any-return]

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        if kwargs.get("dry_run", False):
            self._cache_staff = dict()


class FacultyWidget(widgets.ForeignKeyWidget):
    """Ensure a Faculty entry exists for the given staff name."""

    def __init__(self):
        # field is "id" by default
        self._cache_faculty: dict[str, tuple[Staff, bool]] = dict()
        super().__init__(Faculty)

    def clean(self, value: str, row=None, *args, **kwargs) -> Faculty:
        """From the faculty name, tries to get a faculty object.

        Create user and staff if necessary.
        if value is '<unique>' create a default unique faculty
        """
        if not value:
            return Faculty.get_unique_default()

        prefix, first, middle, last, suffix = split_name(value)
        username = mk_username(first, last, prefix_len=2)

        # ? Should I use Peoplerepository.get_or_create_faculty?
        # ... Not obvious as I would need to pass the whole row.
        # staff = StaffProfileWidget().clean(value, row, *args, **kwargs)
        import pdb

        pdb.set_trace()

        faculty, _ = self._cache_faculty.setdefault(
            username,
            Faculty.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first.capitalize(),
                    "last_name": last.capitalize(),
                    "password": TEST_PW,
                    "name_prefix": prefix,
                    "middle_name": middle,
                    "name_suffix": suffix,
                },
            ),
        )

        return cast(Faculty, faculty)

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        if kwargs.get("dry_run", False):
            self.cache_faculty = dict()


class StudentUserWidget(widgets.ForeignKeyWidget):
    """Ensure a Student User exists."""

    def __init__(self):
        # field is "id" by default
        super().__init__(User)
        self._cache_username: dict[str, str] = dict()
        self._exclude_username = set()
        self._cache_student: dict[str, tuple[Student, bool]] = dict()

    def clean(self, value: str, row=None, *args, **kwargs) -> Student | None:
        """From the student name (and an id), gets a Student object.

        Create user and student objects if necessary.
        Use the extra column student_id to desambiguate sames names
        and create uniq username.
        """

        if not value:
            return None

        std_fullname = (value or "").strip()
        prefix, first, middle, last, suffix = split_name(std_fullname)

        assert "student_id" in row
        stdid = row.get("student_id")
        # in case we get same first, last & middle name for different id,
        # we create a new username because the previous one will be in _exclude
        username = self._cache_username.get(
            stdid,
            Student.mk_username(first, last, middle, exclude=self._exclude_username),
        )
        self._cache_username[stdid] = username
        self._exclude_username |= {username}

        user, _ = self._cache_student.setdefault(
            username,
            Student.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first.capitalize(),
                    "last_name": last.capitalize(),
                    "password": TEST_PW,
                },
            ),
        )
        return user

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        if kwargs.get("dry_run", False):
            self._exclude_username = set()
            self.cache_username = dict()
            self.cache_student = dict()
