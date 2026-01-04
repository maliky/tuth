"""People.Admin.Widgets module.

Usage::

    >>> from app.people.admin.widgets import StaffProfileWidget
    >>> widget = StaffProfileWidget()
    >>> staff = widget.clean("Dr. Jane Doe")
    >>> print(staff.long_name)
"""

from typing import Any, Hashable, cast

from django.contrib.auth.models import User
from import_export import widgets

from app.academics.admin.widgets import CurriculumWidget
from app.academics.models.curriculum import Curriculum
from app.people.models.donor import Donor
from app.people.models.faculty import Faculty
from app.people.models.staffs import Staff
from app.people.models.student import Student
from app.people.utils import (
    cached_entity,
    default_password,
    mk_password,
    parse_name,
)
from app.shared.utils import get_in_row


class StaffProfileWidget(widgets.ForeignKeyWidget):

    def __init__(self):
        self._cache_staff: dict[Hashable, Staff] = {}
        super().__init__(Staff, field="staff_id")

    def clean(self, value, row=None, *args, **kwargs) -> Staff:
        """Create or fetch a Staff from a name.

        The widget splits the name, creates the corresponding User if
        needed.  It return or creates a Staff.
        """
        if not value:
            return Staff.get_unique_default()

        _n = parse_name(value, fallback_last="Staff")
        username = get_in_row("username", row)
        if not username:
            username = Staff.mk_username(_n.first, _n.last)

        found_user = Staff.objects._find_by_name(
            first_name=_n.first, last_name=_n.last, middle_name=_n.middle
        )
        if found_user:
            existing_staff = Staff.objects.filter(user=found_user).first()
            if existing_staff:
                return existing_staff

        def _create_staff() -> Staff:
            staff, _ = Staff.objects.get_or_create(
                username=username, defaults=_n.to_dict()
            )
            staff.user.set_password(default_password(_n.first, _n.last))
            staff.user.save(update_fields=["password"])
            return cast(Staff, staff)

        staff_obj = cached_entity(self._cache_staff, username, _create_staff)
        return staff_obj

    def render(self, value, obj=None) -> str:
        """For the value (staff) for export."""
        return value.long_name if value else ""  # type: ignore[no-any-return]

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        self._cache_staff = dict()


class FacultyWidget(widgets.ForeignKeyWidget):
    """Ensure a Faculty entry exists for the given staff name."""

    def __init__(self):
        # field is "id" by default
        self._cache_faculty: dict[Hashable, Faculty] = {}
        self._cache_exclude_username = set()
        super().__init__(Faculty)

    def clean(self, value: str, row=None, *args, **kwargs) -> Faculty:
        """From the faculty name, tries to get a faculty object.

        Create user and staff if necessary.
        if value is '<unique>' create a default unique faculty
        """
        if not value:
            # return Faculty.get_unique_default()
            return Faculty.get_default()

        _n = parse_name(value, fallback_last="Faculty")
        username = Faculty.mk_username(
            _n.first, _n.last, exclude=self._cache_exclude_username
        )
        self._cache_exclude_username |= {username}

        def _create_faculty() -> Faculty:
            faculty, _ = Faculty.objects.get_or_create(
                username=username, defaults=_n.to_dict()
            )
            faculty.staff_profile.user.set_password(default_password(_n.first, _n.last))
            faculty.staff_profile.user.save(update_fields=["password"])
            return cast(Faculty, faculty)

        faculty_obj = cached_entity(self._cache_faculty, username, _create_faculty)
        return faculty_obj

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        self.cache_faculty = dict()


class StudentUserWidget(widgets.ForeignKeyWidget):
    """Ensure a Student User exists."""

    def __init__(self):
        # field is "id" by default
        super().__init__(User)
        self._cache_username: dict[str, str] = {}
        self._exclude_username = set()
        self._cache_student: dict[str, Student] = {}

    def clean(self, value: str, row=None, *args, **kwargs) -> Student | None:
        """From the student name (and an id), gets a Student object.

        Create user and student objects if necessary.
        Use the extra column student_id to desambiguate sames names
        and create uniq username.
        """
        if not value:
            return None

        std_fullname = (value or "").strip()
        _n = parse_name(
            std_fullname, fallback_first="Student", fallback_last=std_fullname
        )

        assert "student_id" in row
        stdid = row.get("student_id")
        # in case we get same first, last & middle name for different id,
        # we create a new username because the previous one will be in _exclude
        if stdid not in self._cache_student:
            username = Student.mk_username(
                _n.first, _n.last, _n.middle, exclude=self._exclude_username
            )
            self._cache_username[stdid] = username
            self._exclude_username |= {username}
            student, _ = Student.objects.get_or_create(
                username=username, defaults=_n.to_dict()
            )
            student.set_password(default_password(_n.first, _n.last))
            student.save(update_fields=["password"])
            self._cache_student[stdid] = student

        return self._cache_student[stdid]

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        self._exclude_username = set()
        self.cache_username = dict()
        self.cache_student = dict()


class GradeStudentWidget(widgets.ForeignKeyWidget):
    """Create or resolve a Student using a student_id when missing."""

    def __init__(self):
        super().__init__(Student, field="student_id")
        self._cache_student: dict[str, Student] = {}
        self.curriculum_w = CurriculumWidget()

    def clean(self, value, row=None, *args, **kwargs) -> Student:
        """Return the Student tied to the identifier, creating it if needed."""
        student_id = (value or "").strip()
        if not student_id:
            return Student.get_default()

        cached = self._cache_student.get(student_id)
        if cached is not None:
            return cached

        existing = Student.objects.filter(student_id=student_id).first()
        if existing:
            self._cache_student[student_id] = existing
            return existing

        # Here it means student does not exists and we need to create it

        curriculum_value = get_in_row("curriculum", row)
        curriculum = self.curriculum_w.clean(value=curriculum_value, row=row)
        if curriculum is None:
            curriculum = Curriculum.get_default()

        first_name = get_in_row("student_first_name", row)
        last_name = get_in_row("student_last_name", row)
        _n = parse_name(
            # Return vars with something.
            " ".join(filter(None, [first_name, last_name])).strip(),
            fallback_first="Student",
            fallback_last=student_id,
        )

        username = Student.mk_username(_n.first, _n.last)
        password = default_password(_n.first, _n.last)
        user = User.objects.create_user(
            username=username,
            first_name=_n.first,
            last_name=_n.last,
            password=password,
        )

        student = Student(
            user=user,
            curriculum=curriculum,
            student_id=student_id,
        )
        student.save()

        self._cache_student[student_id] = student

        return student


class DonorUserWidget(widgets.ForeignKeyWidget):
    """Create or resolve a User for Donor imports."""

    def __init__(self):
        super().__init__(User)
        self._cache_user: dict[str, User] = {}

    def clean(self, value, row=None, *args, **kwargs) -> User:
        """Return or create a User from the donor name."""
        raw_name = (value or "").strip()
        if not raw_name:
            return Donor.get_default().user

        cached = self._cache_user.get(raw_name)
        if cached:
            return cached

        _n = parse_name(raw_name, fallback_last="Donor")
        username = Donor.mk_username(_n.first, _n.last)

        _defaults = {"first_name": _n.first, "last_name": _n.last}
        user, created = User.objects.get_or_create(username=username, defaults=_defaults)
        if created:
            user.set_password(mk_password(_n.first, _n.last))
            user.save(update_fields=["password"])

        self._cache_user[raw_name] = user
        return user


class StaffUserWidget(widgets.ForeignKeyWidget):
    """Create or resolve a User from a username."""

    def __init__(self):
        super().__init__(User)
        self._cache_user: dict[str, User] = {}

    def clean(self, value, row=None, *args, **kwargs) -> User:
        """Return or create a User from the donor name."""
        username = (value or "").strip()
        if not username:
            return Staff.get_default().user

        cached = self._cache_user.get(username)
        if cached:
            return cached

        fullname = get_in_row("fullname", row)
        _n = parse_name(fullname, fallback_last="Donor")

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"first_name": _n.first, "last_name": _n.last},
        )
        if created:
            user.set_password(mk_password(_n.first, _n.last))
            user.save(update_fields=["password"])

        self._cache_user[raw_name] = user
        return user


class UserStudentWidget(widgets.ForeignKeyWidget):
    """Import a User from an existing student."""

    def __init__(self):
        # field is "id" by default
        super().__init__(User)
        self._cache_username: dict[str, str] = dict()
        self._exclude_username = set()
        self._cache_user: dict[str, User] = dict()

    def clean(self, value: str, row=None, *args, **kwargs) -> User | None:
        """From the student name (and an id), gets a Student object."""
        if not value:
            return None

        stdid = get_in_row("student_id", row)
        if not stdid:
            return None

        fullname = (value or "").strip()
        _n = parse_name(fullname, fallback_first="Student", fallback_last=fullname)

        if stdid not in self._cache_user:
            username = get_in_row("username", row)
            if not username:
                username = Student.mk_username(
                    _n.first, _n.last, _n.middle, exclude=self._exclude_username
                )
            self._cache_username[stdid] = username
            self._exclude_username |= {username}
            user, _ = User.objects.get_or_create(
                username=username, defaults={"first_name": _n.first, "last_name": _n.last}
            )
            user.set_password(default_password(_n.first, _n.last))
            user.save(update_fields=["password"])

            self._cache_user[stdid] = user

        return self._cache_user[stdid]

    def after_import(self, dataset, result, **kwargs):
        """Remove any cache which may be present after import."""
        self._exclude_username = set()
        self.cache_username = dict()
        self.cache_student = dict()
